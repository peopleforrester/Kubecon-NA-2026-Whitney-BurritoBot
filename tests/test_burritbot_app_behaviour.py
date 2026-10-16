# ABOUTME: Behavioural tests for the BurritBot FastAPI app — /healthz and /chat called in-process.
# ABOUTME: Static tests need no network; the live test sends a real prompt to Vertex AI.

from __future__ import annotations

import importlib.util
from types import ModuleType

import pytest
from fastapi.testclient import TestClient

from conftest import GCP_PROJECT_ID, GCP_REGION, PROJECT_ROOT


pytestmark = pytest.mark.phase6

APP_SOURCE = PROJECT_ROOT / "apps" / "burritbot" / "app.py"

# The pin app.py falls back to when MODEL_NAME is unset (the tests unset it).
PINNED_MODEL = "gemini-3-pro"

# app.py reads these at import time, so each test loads a fresh module
# under an environment it controls.
APP_ENV_VARS = (
    "MODEL_NAME",
    "GOOGLE_CLOUD_PROJECT",
    "GOOGLE_CLOUD_LOCATION",
    "BURRITBOT_GUARDED",
)


def _load_app(monkeypatch: pytest.MonkeyPatch, **env: str) -> ModuleType:
    """Import apps/burritbot/app.py as a new module under exactly ``env``."""
    for name in APP_ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    spec = importlib.util.spec_from_file_location("burritbot_app_under_test", APP_SOURCE)
    assert spec is not None and spec.loader is not None, f"cannot load {APP_SOURCE}"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.static
def test_healthz_reports_unguarded_gemini_3_pro_by_default(monkeypatch) -> None:
    client = TestClient(_load_app(monkeypatch).app)
    resp = client.get("/healthz")
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"status": "ok", "model": PINNED_MODEL, "guarded": False}


@pytest.mark.static
@pytest.mark.parametrize("flag", ["true", "TRUE", "True"])
def test_healthz_reports_guarded_when_flag_set(monkeypatch, flag: str) -> None:
    """The guarded Deployment sets BURRITBOT_GUARDED; the flag is case-insensitive."""
    client = TestClient(_load_app(monkeypatch, BURRITBOT_GUARDED=flag).app)
    body = client.get("/healthz").json()
    assert body["guarded"] is True, body


@pytest.mark.static
def test_healthz_treats_other_flag_values_as_unguarded(monkeypatch) -> None:
    client = TestClient(_load_app(monkeypatch, BURRITBOT_GUARDED="yes").app)
    assert client.get("/healthz").json()["guarded"] is False


@pytest.mark.static
@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"prompt": ""},
        {"prompt": "x" * 2001},
        {"message": "teach me some salsa dance moves"},
    ],
    ids=["missing-body-field", "empty-prompt", "prompt-over-2000-chars", "wrong-field-name"],
)
def test_chat_rejects_invalid_payloads_before_calling_the_model(monkeypatch, payload) -> None:
    """Pydantic validation returns 422 without ever reaching Vertex AI."""
    client = TestClient(_load_app(monkeypatch).app)
    resp = client.post("/chat", json=payload)
    assert resp.status_code == 422, resp.text


@pytest.mark.static
def test_chat_accepts_a_2000_char_prompt_past_validation(monkeypatch) -> None:
    """The upper bound is inclusive: 2000 chars passes validation and reaches the model call."""
    client = TestClient(_load_app(monkeypatch).app)
    resp = client.post("/chat", json={"prompt": "x" * 2000})
    # No GOOGLE_CLOUD_PROJECT, so the model call fails with 502 rather than 422.
    assert resp.status_code == 502, resp.text


@pytest.mark.static
def test_chat_fails_explicitly_without_gcp_project(monkeypatch) -> None:
    """No project means a 502 naming the missing variable, not a silent default."""
    client = TestClient(_load_app(monkeypatch).app)
    resp = client.post("/chat", json={"prompt": "teach me some salsa dance moves"})
    assert resp.status_code == 502, resp.text
    detail = resp.json()["detail"]
    assert detail.startswith("upstream model call failed:"), detail
    assert "GOOGLE_CLOUD_PROJECT is not set" in detail, detail


@pytest.mark.live
def test_chat_returns_a_real_vertex_reply(monkeypatch) -> None:
    """A canonical Act 1 prompt round-trips through Vertex AI with token usage."""
    module = _load_app(
        monkeypatch,
        GOOGLE_CLOUD_PROJECT=GCP_PROJECT_ID,
        GOOGLE_CLOUD_LOCATION=GCP_REGION,
    )
    client = TestClient(module.app)
    resp = client.post("/chat", json={"prompt": "teach me some salsa dance moves"})
    assert resp.status_code == 200, (
        f"/chat against Vertex AI in project {GCP_PROJECT_ID} ({GCP_REGION}) "
        f"failed; needs Application Default Credentials with Vertex AI access: "
        f"{resp.status_code} {resp.text}"
    )
    body = resp.json()
    assert body["reply"].strip(), body
    assert body["model"] == PINNED_MODEL, body
    assert body["guarded"] is False, body
    assert body["input_tokens"] > 0, body
    assert body["output_tokens"] > 0, body
