# ABOUTME: Phase 7 audience limit tests (#88, question 157) — each browser token gets its own budget,
# ABOUTME: one address is capped by a ceiling, a tokenless phone falls back to its address; numbers come from the overlay.

from __future__ import annotations

import importlib.util
import re
import shutil
import socket
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest
import yaml
from fastapi.testclient import TestClient

from conftest import PROJECT_ROOT
from helpers.manifest_graph import kustomization_files, load_manifests


pytestmark = pytest.mark.phase7

FRONTEND_DIR = PROJECT_ROOT / "apps" / "audience-frontend"
BACKEND_FILE = FRONTEND_DIR / "backend" / "main.py"
APP_JS = FRONTEND_DIR / "static" / "app.js"
BASE_DEPLOYMENT = FRONTEND_DIR / "k8s" / "deployment.yaml"
AUDIENCE_APP = PROJECT_ROOT / "gitops" / "apps" / "30-audience.yaml"
PLATFORM_BASE = "deploy/audience"
OVERLAY = PROJECT_ROOT / "presentations" / "kubecon-na-2026" / "deploy" / "audience"

TOKEN_ENV = "AUDIENCE_TOKEN_LIMIT"
ADDRESS_ENV = "AUDIENCE_ADDRESS_LIMIT"
TOKEN_HEADER = "X-Audience-Token"

# Question 157: 10 a minute per browser (the spec's per-person number), and
# 300 a minute per address, a room of about 30 active phones at full rate.
DELIVERY_LIMITS = {TOKEN_ENV: "10/minute", ADDRESS_ENV: "300/minute"}

GFE_PEER = "35.191.12.34"  # a Google Front End proxy, as the pod sees it
LB_IP = "34.120.10.20"  # the Gateway's forwarding-rule address
VENUE_NAT = "203.0.113.5"  # the venue Wi-Fi's one public address
CELL_PHONE = "198.51.100.7"


def _load_backend(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, BACKEND_FILE)
    assert spec and spec.loader, f"cannot load {BACKEND_FILE}"
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _refused_port() -> int:
    """A loopback port with nothing listening, so the upstream call fails at once."""
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _token(n: int) -> str:
    return f"{n:032x}"


@pytest.fixture
def ask(monkeypatch: pytest.MonkeyPatch):
    """Build the app with the given limits and return ask(address, token) -> (status, body)."""

    def build(token_limit: str, address_limit: str):
        monkeypatch.setenv(TOKEN_ENV, token_limit)
        monkeypatch.setenv(ADDRESS_ENV, address_limit)
        monkeypatch.setenv("BURRITBOT_UNGUARDED_URL", f"http://127.0.0.1:{_refused_port()}")
        client = TestClient(_load_backend("audience_frontend_main_token").create_app(),
                            client=(GFE_PEER, 40000))

        def send(address: str, token: str | None = None) -> tuple[int, dict]:
            headers = {"X-Forwarded-For": f"{address},{LB_IP}"}
            if token is not None:
                headers[TOKEN_HEADER] = token
            resp = client.post("/chat", json={"prompt": "teach me some salsa dance moves"},
                               headers=headers)
            return resp.status_code, resp.json()

        return send

    return build


def _statuses(results: list[tuple[int, dict]]) -> list[int]:
    return [status for status, _ in results]


# --- the limits, as the backend applies them ---------------------------------


@pytest.mark.static
def test_each_browser_behind_one_venue_nat_has_its_own_budget(ask) -> None:
    """Eleven prompts from one browser hit 429; the browser beside it on the same Wi-Fi is still served."""
    send = ask(**{"token_limit": "10/minute", "address_limit": "300/minute"})
    # No BurritBot is listening, so a prompt inside the budget is a 502.
    assert _statuses([send(VENUE_NAT, _token(1)) for _ in range(10)]) == [502] * 10
    status, body = send(VENUE_NAT, _token(1))
    assert status == 429, "the 11th prompt from one browser in a minute was not limited"
    assert body["limit"] == "phone", body
    assert send(VENUE_NAT, _token(2))[0] == 502, "a second browser on the venue NAT shared the first one's budget"


@pytest.mark.static
def test_one_address_is_capped_however_many_tokens_it_sends(ask) -> None:
    """Clearing the token mints a fresh budget; the per-address ceiling still stops it."""
    send = ask(token_limit="2/minute", address_limit="5/minute")
    assert _statuses([send(VENUE_NAT, _token(n)) for n in range(5)]) == [502] * 5
    status, body = send(VENUE_NAT, _token(99))
    assert status == 429, "a fresh token got past the per-address ceiling"
    assert body["limit"] == "network", body
    assert send(CELL_PHONE, _token(99))[0] == 502, "the ceiling on one address limited another"


@pytest.mark.static
def test_a_browser_without_a_token_falls_back_to_the_per_address_limit(ask) -> None:
    send = ask(token_limit="10/minute", address_limit="300/minute")
    assert _statuses([send(VENUE_NAT) for _ in range(10)]) == [502] * 10
    status, body = send(VENUE_NAT)
    assert status == 429, "a tokenless phone was not held to the per-address limit"
    assert body["limit"] == "phone", body
    assert send(CELL_PHONE)[0] == 502, "a tokenless phone on another address shared the budget"
    assert send(VENUE_NAT, _token(1))[0] == 502, "a browser with a token was charged the tokenless budget"


@pytest.mark.static
@pytest.mark.parametrize("token", ["", "abc", _token(0xABC).upper(), _token(1) + "0", "z" * 32])
def test_a_malformed_token_is_refused(ask, token: str) -> None:
    send = ask(token_limit="10/minute", address_limit="300/minute")
    status, body = send(VENUE_NAT, token)
    assert status == 400, body
    assert TOKEN_HEADER in body["detail"]


@pytest.mark.static
@pytest.mark.parametrize("missing", [TOKEN_ENV, ADDRESS_ENV])
def test_the_app_refuses_to_start_without_a_limit(monkeypatch: pytest.MonkeyPatch, missing: str) -> None:
    for env, value in DELIVERY_LIMITS.items():
        monkeypatch.setenv(env, value)
    monkeypatch.delenv(missing)
    with pytest.raises(RuntimeError, match=missing):
        _load_backend("audience_frontend_main_unset")


@pytest.mark.static
@pytest.mark.parametrize("value", ["ten a minute", "10/fortnight", "  "])
def test_the_app_refuses_to_start_with_a_limit_it_cannot_parse(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    monkeypatch.setenv(TOKEN_ENV, DELIVERY_LIMITS[TOKEN_ENV])
    monkeypatch.setenv(ADDRESS_ENV, value)
    with pytest.raises(RuntimeError, match=ADDRESS_ENV):
        _load_backend("audience_frontend_main_bad")


@pytest.mark.static
def test_config_reports_both_limits(monkeypatch: pytest.MonkeyPatch) -> None:
    for env, value in DELIVERY_LIMITS.items():
        monkeypatch.setenv(env, value)
    body = TestClient(_load_backend("audience_frontend_main_config").create_app()).get("/config").json()
    assert body["token_limit"] == DELIVERY_LIMITS[TOKEN_ENV]
    assert body["address_limit"] == DELIVERY_LIMITS[ADDRESS_ENV]


# --- the page sends a per-browser token --------------------------------------


@pytest.mark.static
def test_page_keeps_a_random_token_in_local_storage_and_sends_it() -> None:
    js = APP_JS.read_text(encoding="utf-8")
    assert "localStorage" in js, "app.js does not keep the token across reloads"
    assert "crypto.getRandomValues" in js, "app.js does not draw the token from the browser's CSPRNG"
    assert re.search(rf"[\"']{TOKEN_HEADER}[\"']", js), f"app.js never sends {TOKEN_HEADER}"
    # The page checks a stored token with the same shape the backend accepts.
    assert "/^[0-9a-f]{32}$/" in js


@pytest.mark.static
def test_page_tells_a_capped_network_from_a_capped_phone() -> None:
    js = APP_JS.read_text(encoding="utf-8")
    assert '"network"' in js and "cellular" in js, "a network-ceiling 429 does not suggest cellular"


# --- the numbers live in the delivery overlay --------------------------------


def _docs(path: Path) -> list[dict]:
    return [d for d in yaml.safe_load_all(path.read_text(encoding="utf-8")) if d]


def _overlay_kustomization() -> dict:
    return yaml.safe_load((OVERLAY / "kustomization.yaml").read_text(encoding="utf-8"))


def _overlay_patches() -> list[dict]:
    return [doc for entry in _overlay_kustomization()["patches"] for doc in _docs(OVERLAY / entry["path"])]


@pytest.mark.static
def test_audience_application_syncs_the_delivery_overlay() -> None:
    app = next(d for d in _docs(AUDIENCE_APP) if d["kind"] == "Application")
    assert (PROJECT_ROOT / app["spec"]["source"]["path"]).resolve() == OVERLAY.resolve()
    resources = [(OVERLAY / r).resolve() for r in _overlay_kustomization()["resources"]]
    assert resources == [(PROJECT_ROOT / PLATFORM_BASE).resolve()], (
        f"{OVERLAY} must wrap {PLATFORM_BASE} and nothing else"
    )


@pytest.mark.static
def test_overlay_sets_the_delivery_limits() -> None:
    patches = [p for p in _overlay_patches() if p["kind"] == "Deployment"]
    assert len(patches) == 1, f"expected one Deployment patch in {OVERLAY}, got {len(patches)}"
    patch = patches[0]
    assert (patch["metadata"]["namespace"], patch["metadata"]["name"]) == ("audience", "audience-frontend")
    containers = {c["name"]: c for c in patch["spec"]["template"]["spec"]["containers"]}
    env = {e["name"]: e.get("value") for e in containers["audience-frontend"]["env"]}
    assert {k: env.get(k) for k in DELIVERY_LIMITS} == DELIVERY_LIMITS


@pytest.mark.static
def test_every_overlay_patch_targets_an_object_the_base_renders() -> None:
    rendered = kustomization_files(PROJECT_ROOT, PROJECT_ROOT / PLATFORM_BASE)
    objects = {(m.kind, m.namespace, m.name) for m in load_manifests(PROJECT_ROOT) if m.path in rendered}
    for doc in _overlay_patches():
        key = (doc["kind"], doc["metadata"].get("namespace"), doc["metadata"]["name"])
        assert key in objects, f"{OVERLAY} patches {key}, which {PLATFORM_BASE} does not render"


@pytest.mark.static
def test_base_deployment_leaves_the_limits_to_the_overlay() -> None:
    """Without the overlay the pod refuses to start, rather than run with numbers nobody chose."""
    container = _docs(BASE_DEPLOYMENT)[0]["spec"]["template"]["spec"]["containers"][0]
    names = {e["name"] for e in container.get("env", [])}
    assert not names & set(DELIVERY_LIMITS), f"{BASE_DEPLOYMENT} sets {names & set(DELIVERY_LIMITS)}"


# --- live: kustomize renders the limits the way the patch claims -------------


@pytest.mark.live
def test_kustomize_renders_the_delivery_limits() -> None:
    kubectl = shutil.which("kubectl")
    assert kubectl, "kubectl is not on PATH; this check renders the overlay with `kubectl kustomize`"
    result = subprocess.run([kubectl, "kustomize", str(OVERLAY)], capture_output=True, text=True, check=False)
    assert result.returncode == 0, f"kubectl kustomize {OVERLAY} failed: {result.stderr}"
    deployment = next(d for d in yaml.safe_load_all(result.stdout)
                      if d and d["kind"] == "Deployment" and d["metadata"]["name"] == "audience-frontend")
    env = {e["name"]: e.get("value") for e in deployment["spec"]["template"]["spec"]["containers"][0]["env"]}
    assert {k: env.get(k) for k in DELIVERY_LIMITS} == DELIVERY_LIMITS
    assert "BURRITBOT_TARGET" in env, "the patch replaced the base env instead of merging into it"
