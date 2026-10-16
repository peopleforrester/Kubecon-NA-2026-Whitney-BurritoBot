# ABOUTME: Unguarded BurritBot labels each Vertex AI request with the delivery's cost labels (#82),
# ABOUTME: read from BURRITBOT_DELIVERY, so model spend sums by burritbot-io_delivery in the export.

from __future__ import annotations

import importlib.util
import sys
from types import ModuleType

import pytest
from fastapi.testclient import TestClient
from google.genai import models as genai_models

from conftest import PROJECT_ROOT
from helpers.cost_labels import terraform_cost_labels


BURRITBOT_APP = PROJECT_ROOT / "apps" / "burritbot" / "app.py"
DELIVERY_ENV = "BURRITBOT_DELIVERY"
SLUG = "summit-2027"


def _load(name: str) -> ModuleType:
    """Import a fresh copy of app.py, so it reads the environment as it is now."""
    spec = importlib.util.spec_from_file_location(name, BURRITBOT_APP)
    assert spec and spec.loader, f"cannot load {BURRITBOT_APP}"
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _terraform_cost_labels() -> dict[str, str]:
    return terraform_cost_labels(SLUG)


@pytest.mark.static
def test_request_labels_match_the_terraform_cost_labels(monkeypatch: pytest.MonkeyPatch) -> None:
    """Model calls carry the same keys as the cluster, so one query filter covers both."""
    monkeypatch.setenv(DELIVERY_ENV, SLUG)
    burritbot = _load("burritbot_app_labels")
    assert burritbot.request_labels() == _terraform_cost_labels()


@pytest.mark.static
@pytest.mark.parametrize("value", ["", "   ", "Summit", "2027-summit", "a" * 64, "summit.2027"])
def test_request_labels_refuse_a_missing_or_invalid_delivery(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    """Unset or not a GCP label value: fail, never send an unlabelled or rejected call."""
    monkeypatch.setenv(DELIVERY_ENV, value)
    burritbot = _load("burritbot_app_labels_invalid")
    with pytest.raises(RuntimeError, match=DELIVERY_ENV):
        burritbot.request_labels()


@pytest.mark.static
def test_request_labels_refuse_an_unset_delivery(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(DELIVERY_ENV, raising=False)
    burritbot = _load("burritbot_app_labels_unset")
    with pytest.raises(RuntimeError, match=f"{DELIVERY_ENV} is not set"):
        burritbot.request_labels()


@pytest.mark.static
def test_vertex_request_body_carries_the_labels(monkeypatch: pytest.MonkeyPatch) -> None:
    """The pinned google-genai SDK puts config.labels on the generateContent request itself."""
    monkeypatch.setenv(DELIVERY_ENV, SLUG)
    burritbot = _load("burritbot_app_vertex_config")
    config = burritbot.vertex_config()
    assert config.labels == _terraform_cost_labels()
    assert config.system_instruction == burritbot.SYSTEM_PROMPT

    request: dict = {}
    genai_models._GenerateContentConfig_to_vertex(None, config, request)
    assert request.get("labels") == _terraform_cost_labels(), (
        f"google-genai did not put the labels on the Vertex request: {request}"
    )


@pytest.mark.static
def test_unguarded_chat_fails_without_a_delivery(monkeypatch: pytest.MonkeyPatch) -> None:
    """An unset delivery is a 502 naming the variable, before any Vertex client exists."""
    monkeypatch.delenv("BURRITBOT_GUARDED", raising=False)
    monkeypatch.delenv(DELIVERY_ENV, raising=False)
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "label-check-project")
    burritbot = _load("burritbot_app_unguarded_no_delivery")
    resp = TestClient(burritbot.app).post("/chat", json={"prompt": "teach me some salsa dance moves"})
    assert resp.status_code == 502, resp.text
    assert f"{DELIVERY_ENV} is not set" in resp.json()["detail"]
    assert burritbot._client.cache_info().currsize == 0, "a Vertex client was built anyway"


@pytest.mark.static
def test_guarded_app_does_not_need_a_delivery(monkeypatch: pytest.MonkeyPatch) -> None:
    """Guarded BurritBot never calls Vertex itself; its labels are the gateway's to set."""
    monkeypatch.setenv("BURRITBOT_GUARDED", "true")
    monkeypatch.setenv("AI_GATEWAY_URL", "http://127.0.0.1:9")
    monkeypatch.delenv(DELIVERY_ENV, raising=False)
    burritbot = _load("burritbot_app_guarded_no_delivery")
    assert "labels" not in burritbot.gateway_request_body("how do I throw a hot dog party")
