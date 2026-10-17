#!/usr/bin/env python3
# ABOUTME: Replays a recorded audience prompt set into the audience frontend's /chat when phones or venue Wi-Fi fail.
# ABOUTME: Paces one browser token under the limit the frontend reports at /config and stops loudly on the first failure.
"""Stand in for the room: send a prompt set to the audience frontend, one at a time.

Run from the presenter laptop, against the public URL or a port-forward that
avoids the venue Wi-Fi:

    kubectl -n audience port-forward svc/audience-frontend 8080:80
    uv run --managed-python --frozen python scripts/replay-prompts.py \\
        --url http://127.0.0.1:8080 --prompts <prompts.yaml> --set audience --rounds 3

Each reply prints with the bot that answered (the frontend's target), so the
same replay runs through Act 1, Cast the Net and Act 2. The replay is one
browser: it sends one token and keeps to that token's limit, so it never
spends the room's budget or trips the per-address ceiling.
"""

from __future__ import annotations

import argparse
import secrets
import sys
import time
from pathlib import Path
from typing import TextIO

import httpx
import yaml
from limits import parse_many


TOKEN_HEADER = "X-Audience-Token"  # apps/audience-frontend/backend/main.py
# Headroom over the limit's exact spacing, so a send never lands on the
# edge of a full window.
PACE_MARGIN = 1.1
# Above the frontend's guarded timeout (GUARDED_TIMEOUT_SECONDS, 125s), so
# a slow guarded reply comes back as the frontend's own error.
CHAT_TIMEOUT_SECONDS = 135.0


class ReplayError(Exception):
    """The prompt set, the frontend's settings or a reply is not what the replay needs."""


def load_prompts(path: Path, set_name: str) -> list[str]:
    """Return the prompts in set_name from a `sets:` YAML file, or raise ReplayError."""
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    sets = doc.get("sets") if isinstance(doc, dict) else None
    if not isinstance(sets, dict):
        raise ReplayError(f"{path} has no `sets:` mapping")
    if set_name not in sets:
        raise ReplayError(f"{path} has no prompt set {set_name!r}; it has {sorted(sets)}")
    prompts = sets[set_name]
    if not prompts or not all(isinstance(p, str) and p.strip() for p in prompts):
        raise ReplayError(f"prompt set {set_name!r} in {path} is empty or has a blank prompt")
    return prompts


def send_interval(limit: str) -> float:
    """Seconds between sends that keep one token under limit (e.g. "10/minute"), with headroom."""
    try:
        items = parse_many(limit)
    except ValueError as exc:
        raise ReplayError(f"cannot read the frontend's token limit {limit!r}: {exc}") from exc
    return max(item.get_expiry() / item.amount for item in items) * PACE_MARGIN


def token_limit(client: httpx.Client) -> str:
    """Return the per-browser /chat limit the frontend reports at /config."""
    url = client.base_url.join("/config")
    resp = client.get("/config")
    if resp.status_code != 200:
        raise ReplayError(f"{url} returned HTTP {resp.status_code}: {resp.text[:500]}")
    try:
        limit = resp.json().get("token_limit")
    except ValueError as exc:
        raise ReplayError(f"{url} did not return JSON: {resp.text[:500]}") from exc
    if not limit:
        raise ReplayError(f"{url} reports no token_limit")
    return limit


def replay(client: httpx.Client, prompts: list[str], rounds: int, out: TextIO, err: TextIO) -> int:
    """Send prompts `rounds` times through client; return 0, or 1 at the first failure."""
    chat_url = client.base_url.join("/chat")
    try:
        limit = token_limit(client)
        interval = send_interval(limit)
    except httpx.HTTPError as exc:
        print(f"replay-prompts: {client.base_url.join('/config')} unreachable: {exc}", file=err)
        return 1
    except ReplayError as exc:
        print(f"replay-prompts: {exc}", file=err)
        return 1

    sequence = prompts * rounds
    headers = {TOKEN_HEADER: secrets.token_hex(16)}
    print(
        f"replay-prompts: {len(sequence)} prompts to {chat_url}, one every {interval:.1f}s "
        f"(token limit {limit})",
        file=out,
        flush=True,
    )
    last_send: float | None = None
    for n, prompt in enumerate(sequence, start=1):
        if last_send is not None:
            time.sleep(max(0.0, last_send + interval - time.monotonic()))
        last_send = time.monotonic()
        where = f"prompt {n}/{len(sequence)} {prompt!r}"
        try:
            resp = client.post("/chat", json={"prompt": prompt}, headers=headers)
        except httpx.HTTPError as exc:
            print(f"replay-prompts: {where}: {chat_url} unreachable: {exc}", file=err)
            return 1
        if resp.status_code != 200:
            print(f"replay-prompts: {where} got HTTP {resp.status_code} from {chat_url}: {resp.text[:500]}", file=err)
            return 1
        body = resp.json()
        if "target" not in body or "reply" not in body:
            print(f"replay-prompts: {where}: reply from {chat_url} has no target or reply: {body}", file=err)
            return 1
        print(f"[{n}/{len(sequence)}] {body['target']}: {prompt}", file=out)
        for line in body["reply"].splitlines() or [""]:
            print(f"    {line}", file=out)
        out.flush()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--url", required=True, help="audience frontend base URL, e.g. http://127.0.0.1:8080")
    parser.add_argument("--prompts", required=True, type=Path, help="prompt set file (a `sets:` mapping)")
    parser.add_argument("--set", required=True, dest="set_name", help="which set in the file to send")
    parser.add_argument("--rounds", type=int, default=1, help="times to send the set (default 1)")
    args = parser.parse_args(argv)
    if args.rounds < 1:
        parser.error("--rounds must be at least 1")

    try:
        prompts = load_prompts(args.prompts, args.set_name)
    except (OSError, ReplayError) as exc:
        print(f"replay-prompts: {exc}", file=sys.stderr)
        return 1
    try:
        with httpx.Client(base_url=args.url, timeout=CHAT_TIMEOUT_SECONDS) as client:
            return replay(client, prompts, args.rounds, sys.stdout, sys.stderr)
    except KeyboardInterrupt:
        print("replay-prompts: stopped", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
