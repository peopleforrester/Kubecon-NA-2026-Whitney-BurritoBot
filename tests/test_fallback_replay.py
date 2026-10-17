# ABOUTME: The live-demo fallback (#103): a replayable audience prompt set and the script that sends it to /chat.
# ABOUTME: Holds the RUNBOOK's worst case to files that exist, the set to the canonical asks and the rails, the replay to the limit.

from __future__ import annotations

import importlib.util
import io
import re
import socket
import stat
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest
import yaml
from fastapi.testclient import TestClient
from nemoguardrails import LLMRails

from conftest import PROJECT_ROOT
from helpers.kubectl_helpers import port_forward
from helpers.nemo_rails import check, mounted_rails
from helpers.static_assets import file_has_aboutme


TALK_DIR = PROJECT_ROOT / "presentations" / "kubecon-na-2026"
RUNBOOK = TALK_DIR / "docs" / "RUNBOOK.md"
FALLBACK_DIR = TALK_DIR / "fallback"
FALLBACK_README = FALLBACK_DIR / "README.md"
PROMPTS = FALLBACK_DIR / "prompts.yaml"
REPLAY_SCRIPT = PROJECT_ROOT / "scripts" / "replay-prompts.py"
FRONTEND_BACKEND = PROJECT_ROOT / "apps" / "audience-frontend" / "backend" / "main.py"
DELIVERY_AUDIENCE = TALK_DIR / "deploy" / "audience" / "delivery-audience.yaml"

# The asks the audience sends from their phones (AGENTS.md, RUNBOOK Act 1).
CANONICAL_ACT1_PROMPTS = (
    "teach me some salsa dance moves",
    "how do I throw a hot dog party",
    "recommend karaoke songs for a wedding",
)
# The frontend's ChatRequest refuses longer prompts with a 422.
MAX_PROMPT_CHARS = 2000
# What the old worst-case step pointed at (#75 row 9): a deck that never existed.
OLD_WORST_CASE = "5. **Worst case:** swap to the static screenshots deck in\n   `docs/fallback-deck/`."


def _load(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader, f"cannot load {path}"
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def replay() -> ModuleType:
    return _load(REPLAY_SCRIPT, "replay_prompts")


def _overlay_limits() -> dict[str, str]:
    """The delivery overlay's /chat limits, which the frontend refuses to start without."""
    doc = yaml.safe_load(DELIVERY_AUDIENCE.read_text(encoding="utf-8"))
    (container,) = doc["spec"]["template"]["spec"]["containers"]
    return {e["name"]: e["value"] for e in container["env"]}


@pytest.fixture
def frontend(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """The real audience frontend, its unguarded upstream on a port nothing listens on."""
    for name, value in _overlay_limits().items():
        monkeypatch.setenv(name, value)
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        closed = s.getsockname()[1]
    monkeypatch.setenv("BURRITBOT_TARGET", "burritbot-unguarded")
    monkeypatch.setenv("BURRITBOT_UNGUARDED_URL", f"http://127.0.0.1:{closed}")
    return TestClient(_load(FRONTEND_BACKEND, "audience_frontend_for_replay").create_app())


def _prompt_sets() -> dict[str, list[str]]:
    return yaml.safe_load(PROMPTS.read_text(encoding="utf-8"))["sets"]


def _section(text: str, heading: str) -> str:
    match = re.search(rf"^## {re.escape(heading)}\b.*?$(.*?)(?=^## |\Z)", text, re.M | re.S)
    assert match, f"no '## {heading}' section"
    return match.group(1)


def _missing_paths(text: str) -> list[str]:
    """Backticked repo paths in text that are neither a file nor a directory.

    A path has a slash, no spaces, and starts with a letter, so a limit like
    `10/minute` is not one.
    """
    paths = set(re.findall(r"`([A-Za-z][\w.-]*(?:/[\w.-]*)+)`", text))
    return sorted(p for p in paths if not (PROJECT_ROOT / p).exists())


# --- The RUNBOOK's worst case points at something real ------------------


@pytest.mark.static
def test_rollback_names_only_paths_that_exist() -> None:
    rollback = _section(RUNBOOK.read_text(encoding="utf-8"), "Rollback")
    assert not _missing_paths(rollback), f"RUNBOOK Rollback names paths that do not exist: {_missing_paths(rollback)}"


@pytest.mark.static
def test_path_check_catches_the_old_missing_deck() -> None:
    """The check above is not vacuous: the pre-#103 worst-case line fails it."""
    assert _missing_paths(OLD_WORST_CASE) == ["docs/fallback-deck/"]


@pytest.mark.static
def test_rollback_replays_the_prompt_set_when_phones_or_wifi_fail() -> None:
    rollback = " ".join(_section(RUNBOOK.read_text(encoding="utf-8"), "Rollback").split())
    script = REPLAY_SCRIPT.relative_to(PROJECT_ROOT).as_posix()
    prompts = PROMPTS.relative_to(PROJECT_ROOT).as_posix()
    assert script in rollback and prompts in rollback, "Rollback never runs the replay on the prompt set"
    assert "port-forward svc/audience-frontend" in rollback, "Rollback gives no way in that avoids the venue Wi-Fi"


@pytest.mark.static
def test_fallback_readme_says_what_waits_on_the_rehearsal() -> None:
    """The videos and the deck are not in the repo until a full rehearsal records them (#18)."""
    text = " ".join(FALLBACK_README.read_text(encoding="utf-8").split())
    for item in ("video", "screenshots deck", "#18"):
        assert item in text, f"fallback README does not mention {item!r}"
    assert PROMPTS.name in text and REPLAY_SCRIPT.name in text


# --- The prompt set ------------------------------------------------------


@pytest.mark.static
def test_prompt_file_has_aboutme() -> None:
    assert file_has_aboutme(PROMPTS), f"{PROMPTS.name} does not start with two ABOUTME lines"


@pytest.mark.static
def test_audience_set_is_the_canonical_act1_asks() -> None:
    """The room sends the lighthearted asks only; attacks stay presenter-driven."""
    assert _prompt_sets()["audience"] == list(CANONICAL_ACT1_PROMPTS)


@pytest.mark.static
def test_every_prompt_fits_the_frontend_limit() -> None:
    for name, prompts in _prompt_sets().items():
        assert prompts, f"prompt set {name!r} is empty"
        for prompt in prompts:
            assert isinstance(prompt, str) and prompt.strip(), f"blank prompt in set {name!r}"
            assert len(prompt) <= MAX_PROMPT_CHARS, f"{prompt[:40]!r}… is over {MAX_PROMPT_CHARS} characters"


@pytest.fixture(scope="module")
def rails(tmp_path_factory: pytest.TempPathFactory) -> LLMRails:
    return mounted_rails(tmp_path_factory.mktemp("config-store"))


@pytest.mark.static
@pytest.mark.parametrize("prompt", CANONICAL_ACT1_PROMPTS)
def test_audience_set_is_caught_by_the_burrito_only_rail(rails: LLMRails, prompt: str) -> None:
    """Replayed into Act 2, each audience ask is redirected to the menu."""
    assert prompt in _prompt_sets()["audience"]
    assert check(rails, [{"role": "user", "content": prompt}]) == ("blocked", "burrito only input")


@pytest.mark.static
def test_menu_set_passes_every_input_rail(rails: LLMRails) -> None:
    """Replayed into Act 2, the menu asks still get answered: the bot ends selling burritos."""
    blocked = {
        prompt: result
        for prompt in _prompt_sets()["menu"]
        if (result := check(rails, [{"role": "user", "content": prompt}])) != ("passed", None)
    }
    assert not blocked, f"menu asks the rails block: {blocked}"


# --- The replay script ---------------------------------------------------


@pytest.mark.static
def test_replay_script_is_executable_with_aboutme() -> None:
    assert REPLAY_SCRIPT.is_file(), f"{REPLAY_SCRIPT} is missing"
    assert REPLAY_SCRIPT.stat().st_mode & stat.S_IXUSR, f"{REPLAY_SCRIPT.name} is not executable"
    assert file_has_aboutme(REPLAY_SCRIPT), f"{REPLAY_SCRIPT.name} does not start with two ABOUTME lines"


@pytest.mark.static
def test_pacing_keeps_one_token_under_the_overlay_limit(replay: ModuleType) -> None:
    """Sends spaced by the interval never put more than the limit's amount in its window."""
    limit = _overlay_limits()["AUDIENCE_TOKEN_LIMIT"]
    assert limit == "10/minute"
    interval = replay.send_interval(limit)
    assert 6.0 < interval < 9.0, interval
    sends_in_a_window = len([t for t in range(1000) if t * interval < 60])
    assert sends_in_a_window <= 10


@pytest.mark.static
def test_pacing_takes_the_strictest_of_several_limits(replay: ModuleType) -> None:
    assert replay.send_interval("100/hour;10/minute") == pytest.approx(36 * replay.PACE_MARGIN)


@pytest.mark.static
def test_pacing_refuses_a_limit_it_cannot_read(replay: ModuleType) -> None:
    with pytest.raises(replay.ReplayError, match="ten a minute"):
        replay.send_interval("ten a minute")


@pytest.mark.static
def test_replay_waits_longer_than_the_frontend_guarded_timeout(replay: ModuleType) -> None:
    """A slow guarded reply comes back as the frontend's error, not the replay's own timeout."""
    backend = FRONTEND_BACKEND.read_text(encoding="utf-8")
    guarded = float(re.search(r"^GUARDED_TIMEOUT_SECONDS = ([\d.]+)", backend, re.M).group(1))
    assert replay.CHAT_TIMEOUT_SECONDS > guarded


@pytest.mark.static
def test_load_prompts_refuses_an_unknown_set(replay: ModuleType) -> None:
    with pytest.raises(replay.ReplayError, match="'encore'.*audience"):
        replay.load_prompts(PROMPTS, "encore")


@pytest.mark.static
def test_replay_reads_the_limit_and_stops_on_the_first_failure(replay: ModuleType, frontend: TestClient) -> None:
    """Against the real frontend with BurritBot down: the first prompt's 502 ends the replay."""
    out, err = io.StringIO(), io.StringIO()
    code = replay.replay(frontend, list(CANONICAL_ACT1_PROMPTS), rounds=2, out=out, err=err)
    assert code == 1
    assert "10/minute" in out.getvalue(), "replay does not say which limit it paces to"
    assert "HTTP 502" in err.getvalue() and CANONICAL_ACT1_PROMPTS[0] in err.getvalue(), err.getvalue()
    assert CANONICAL_ACT1_PROMPTS[1] not in out.getvalue() + err.getvalue(), "replay kept sending after a failure"


@pytest.mark.static
def test_replay_cli_fails_loudly_when_the_frontend_is_unreachable() -> None:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        closed = s.getsockname()[1]
    url = f"http://127.0.0.1:{closed}"
    result = subprocess.run(
        [sys.executable, str(REPLAY_SCRIPT), "--url", url, "--prompts", str(PROMPTS), "--set", "audience"],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 1, result
    assert f"{url}/config" in result.stderr, result.stderr


# --- Live: the replay reaches the deployed frontend --------------------


@pytest.mark.live
@pytest.mark.timeout(600)
def test_replay_reaches_the_deployed_frontend() -> None:
    """One round of the audience set through a port-forward; each reply names the bot that answered."""
    with port_forward("audience", "audience-frontend", 80) as local:
        result = subprocess.run(
            [
                sys.executable, str(REPLAY_SCRIPT),
                "--url", f"http://127.0.0.1:{local}",
                "--prompts", str(PROMPTS),
                "--set", "audience",
            ],
            capture_output=True,
            text=True,
            timeout=540,
            check=False,
        )
    assert result.returncode == 0, result.stderr
    answered = re.findall(r"^\[\d+/\d+\] (burritbot-(?:un)?guarded):", result.stdout, re.M)
    assert len(answered) == len(CANONICAL_ACT1_PROMPTS), result.stdout
