# ABOUTME: Phase 7 refusal tests (#110) — a guardrails 403 reaches the phone as BurritBot sticking to burritos.
# ABOUTME: The backend relays the net's refusal as JSON; app.js renders its detail as a guarded reply, not an error.

from __future__ import annotations

import importlib.util
import json
import re
import sys
from types import ModuleType

import pytest
from fastapi import HTTPException

from conftest import PROJECT_ROOT


pytestmark = pytest.mark.phase7

FRONTEND_DIR = PROJECT_ROOT / "apps" / "audience-frontend"
BACKEND_FILE = FRONTEND_DIR / "backend" / "main.py"
APP_JS = FRONTEND_DIR / "static" / "app.js"
STYLES = FRONTEND_DIR / "static" / "styles.css"

# The body the burritbot-guardrails ext_proc answers a block with
# (ai-gateway/extproc/adapter.py, GuardrailsProcessor._judge).
REFUSAL = {
    "detail": "BurritBot's guardrails stopped this prompt. BurritBot only talks burritos.",
    "blocked_by": "nemo-guardrails",
    "direction": "prompt",
    "findings": {"input": "off topic"},
}


@pytest.fixture(autouse=True)
def _limits(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUDIENCE_TOKEN_LIMIT", "10/minute")
    monkeypatch.setenv("AUDIENCE_ADDRESS_LIMIT", "300/minute")


def _load_backend() -> ModuleType:
    spec = importlib.util.spec_from_file_location("audience_frontend_main_refusal", BACKEND_FILE)
    assert spec and spec.loader, f"cannot load {BACKEND_FILE}"
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


# --- The backend relays the net's refusal --------------------------------


@pytest.mark.static
@pytest.mark.parametrize("direction", ["prompt", "reply"])
def test_a_guardrails_refusal_is_relayed_as_json(direction: str) -> None:
    """The phone gets the net's own JSON, not that JSON quoted inside another detail string."""
    backend = _load_backend()
    refusal = {**REFUSAL, "direction": direction}
    resp = backend.upstream_failure(403, json.dumps(refusal).encode(), "burritbot-guarded")
    assert resp.status_code == 403
    assert resp.media_type == "application/json"
    assert json.loads(resp.body) == {**refusal, "target": "burritbot-guarded"}


@pytest.mark.static
def test_a_rewrite_refusal_is_relayed_too() -> None:
    """The net's other 403, a sanitized prompt the gateway would drop, names its scanner the same way."""
    backend = _load_backend()
    refusal = {
        "detail": "BurritBot's guardrails had to change this prompt, and the AI gateway would send it "
        "to the model unchanged; nothing was let through.",
        "blocked_by": "llm-guard",
        "direction": "prompt",
    }
    resp = backend.upstream_failure(403, json.dumps(refusal).encode(), "burritbot-guarded")
    assert json.loads(resp.body) == {**refusal, "target": "burritbot-guarded"}


@pytest.mark.static
@pytest.mark.parametrize(
    ("status_code", "content"),
    [
        (502, json.dumps({"detail": "could not read a gzip-encoded reply", "blocked_by": "llm-guard"}).encode()),
        (503, json.dumps({"detail": "guardrails are unavailable", "blocked_by": "nemo-guardrails"}).encode()),
        (403, b"RBAC: access denied"),
        (403, b'{"detail": "forbidden"}'),
        (403, b'{"detail": "stopped", "blocked_by": ["llm-guard"]}'),
        (403, b'{"blocked_by": "llm-guard"}'),
        (400, b'{"detail": "BurritBot\'s guardrails could not read this request"}'),
    ],
    ids=["net-502", "net-503", "not-json", "no-scanner", "malformed-scanner", "no-detail", "unreadable-400"],
)
def test_other_upstream_failures_keep_their_status(status_code: int, content: bytes) -> None:
    """Only a 403 that names a scanner and says why is a refusal; the rest stay errors with their status."""
    backend = _load_backend()
    with pytest.raises(HTTPException) as caught:
        backend.upstream_failure(status_code, content, "burritbot-guarded")
    assert caught.value.status_code == status_code
    assert caught.value.detail == content.decode()


@pytest.mark.static
def test_chat_answers_upstream_failures_through_upstream_failure() -> None:
    """/chat hands every upstream error to upstream_failure rather than raising its own HTTPException."""
    source = BACKEND_FILE.read_text(encoding="utf-8")
    assert re.search(r"return upstream_failure\(\s*resp\.status_code,\s*resp\.content,\s*BURRITBOT_TARGET\s*\)", source), (
        "/chat does not return upstream_failure(resp.status_code, resp.content, BURRITBOT_TARGET)"
    )
    assert "HTTPException(status_code=resp.status_code" not in source, (
        "/chat still wraps upstream errors itself, so a refusal reaches the phone as an error"
    )


# --- The page shows it as BurritBot sticking to burritos ------------------


def _function(js: str, name: str) -> str:
    """The source of a top-level `function name(...) { ... }` in app.js, braces balanced."""
    start = js.find(f"function {name}(")
    assert start != -1, f"app.js has no function {name}"
    depth = 0
    for i in range(js.index("{", start), len(js)):
        depth += {"{": 1, "}": -1}.get(js[i], 0)
        if depth == 0:
            return js[start : i + 1]
    raise AssertionError(f"function {name} in app.js never closes")


@pytest.mark.static
def test_page_reads_a_refusal_from_a_403() -> None:
    js = APP_JS.read_text(encoding="utf-8")
    refusal = _function(js, "refusalOf")
    assert "blocked_by" in refusal and "detail" in refusal, (
        "refusalOf does not check the net's blocked_by and detail fields"
    )
    submit = _function(js, "submit")
    assert re.search(r"resp\.status\s*===\s*403", submit), "submit does not read the body of a 403"
    assert "refusalOf(" in submit, "submit does not ask refusalOf whether a 403 is the net's refusal"


@pytest.mark.static
def test_page_renders_a_refusal_as_a_guarded_reply() -> None:
    """The refusal's detail is the reply, labelled with the bot that answered, styled as a reply."""
    js = APP_JS.read_text(encoding="utf-8")
    show = _function(js, "showRefusal")
    assert re.search(r"\.reply\.textContent\s*=\s*refusal\.detail\b", show), (
        "showRefusal does not put the refusal's detail in the reply"
    )
    assert '"reply refused"' in show, "showRefusal does not style the turn as a refusal"
    assert "error" not in show, "a refusal must not be styled as an error"
    assert re.search(r"labelMode\(\s*turn\s*,\s*refusal\.target\s*\)", show), (
        "showRefusal does not label the turn with the bot that answered"
    )
    assert "Something went wrong" not in show


@pytest.mark.static
def test_refused_reply_has_its_own_style() -> None:
    css = STYLES.read_text(encoding="utf-8")
    rule = re.search(r"\.reply\.refused\s*\{([^}]*)\}", css)
    assert rule, "styles.css has no .reply.refused rule"
    assert "--error" not in rule.group(1), "a refusal must not look like an error"
