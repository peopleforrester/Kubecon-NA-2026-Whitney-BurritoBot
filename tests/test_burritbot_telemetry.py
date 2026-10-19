# ABOUTME: BurritBot records and exports its telemetry (#101): a real /chat sends a gen_ai.* span and metric over OTLP.
# ABOUTME: Static tests use an in-process OTLP/gRPC receiver; live tests find the span in Tempo and the metric in Prometheus.

from __future__ import annotations

import importlib.util
import json
import sys
import time
import urllib.parse
import urllib.request
from collections.abc import Iterator
from types import ModuleType

import pytest
import yaml
from fastapi.testclient import TestClient

from conftest import PROJECT_ROOT, closed_loopback_url
from helpers.kubectl_helpers import port_forward
from helpers.otlp_receiver import Received, ReceivedSpan, otlp_receiver


BURRITBOT_APP = PROJECT_ROOT / "apps" / "burritbot" / "app.py"
DEPLOYMENTS = {
    "burritbot-guarded": PROJECT_ROOT / "apps" / "burritbot" / "k8s" / "deployment-guarded.yaml",
    "burritbot-unguarded": PROJECT_ROOT / "apps" / "burritbot" / "k8s" / "deployment-unguarded.yaml",
}
SPAN_KIND_SERVER = 2
SPAN_KIND_CLIENT = 3
STATUS_CODE_ERROR = 2


def _load(name: str) -> ModuleType:
    """Import a fresh copy of app.py, so it reads the environment as it is now."""
    spec = importlib.util.spec_from_file_location(name, BURRITBOT_APP)
    assert spec and spec.loader, f"cannot load {BURRITBOT_APP}"
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _deployment_env(service: str) -> dict[str, str]:
    doc = yaml.safe_load(DEPLOYMENTS[service].read_text(encoding="utf-8"))
    container = next(c for c in doc["spec"]["template"]["spec"]["containers"] if c["name"] == "burritbot")
    return {e["name"]: e.get("value", "") for e in container.get("env", [])}


@pytest.fixture
def receiver(monkeypatch: pytest.MonkeyPatch) -> Iterator[Received]:
    """A real OTLP/gRPC receiver; BurritBot loaded after this fixture exports to it."""
    with otlp_receiver() as (endpoint, received):
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", endpoint)
        yield received


def _chat(burritbot: ModuleType, prompt: str) -> int:
    app = burritbot.app
    status = TestClient(app).post("/chat", json={"prompt": prompt}).status_code
    assert app.state.telemetry.force_flush(), "the SDK could not export to the OTLP receiver"
    return status


def _model_span(received: Received, model: str) -> ReceivedSpan:
    spans = [s for s in received.spans if s.name == f"chat {model}"]
    assert len(spans) == 1, f"expected one 'chat {model}' span, received {[s.name for s in received.spans]}"
    return spans[0]


# --- the app refuses to run blind -------------------------------------------


@pytest.mark.static
@pytest.mark.parametrize("missing", ["OTEL_EXPORTER_OTLP_ENDPOINT", "OTEL_SERVICE_NAME"])
def test_app_refuses_to_start_without_otel_env(monkeypatch: pytest.MonkeyPatch, missing: str) -> None:
    monkeypatch.delenv("BURRITBOT_GUARDED", raising=False)
    monkeypatch.delenv(missing)
    with pytest.raises(RuntimeError, match=missing):
        _load(f"burritbot_app_no_{missing.lower()}")


@pytest.mark.static
@pytest.mark.parametrize("service", sorted(DEPLOYMENTS))
def test_deployment_names_its_service(service: str) -> None:
    """Each Deployment sets what the app requires; the service name is the one the dashboards split on."""
    env = _deployment_env(service)
    assert env.get("OTEL_SERVICE_NAME") == service
    assert env.get("OTEL_EXPORTER_OTLP_ENDPOINT", "").endswith(":4317"), (
        "BurritBot exports OTLP/gRPC; its endpoint must be the collector's gRPC port 4317"
    )


# --- a real /chat records the GenAI span and exports it ---------------------


@pytest.mark.static
def test_guarded_chat_span_is_recorded_and_exported(monkeypatch: pytest.MonkeyPatch, receiver: Received) -> None:
    """A guarded /chat whose gateway is down still leaves a gen_ai.* CLIENT span, exported over OTLP."""
    monkeypatch.setenv("BURRITBOT_GUARDED", "true")
    monkeypatch.setenv("AI_GATEWAY_URL", closed_loopback_url())
    monkeypatch.setenv("OTEL_SERVICE_NAME", "burritbot-guarded")
    burritbot = _load("burritbot_app_telemetry_guarded")
    assert _chat(burritbot, "teach me some salsa dance moves") == 502

    span = _model_span(received=receiver, model=burritbot.MODEL_NAME)
    assert span.kind == SPAN_KIND_CLIENT
    assert span.status_code == STATUS_CODE_ERROR
    assert span.resource["service.name"] == "burritbot-guarded"
    assert span.attributes == {
        "gen_ai.operation.name": "chat",
        "gen_ai.provider.name": "gcp.vertex_ai",
        "gen_ai.request.model": burritbot.MODEL_NAME,
        "gen_ai.request.temperature": burritbot.TEMPERATURE,
        "gen_ai.request.max_tokens": burritbot.MAX_OUTPUT_TOKENS,
        "burritbot.guarded": True,
        "burritbot.layer": "the-eyes",
        "error.type": "RuntimeError",
    }
    server = [s for s in receiver.spans if s.kind == SPAN_KIND_SERVER and s.trace_id == span.trace_id]
    assert [s.name for s in server] == ["POST /chat"], "the model call is not a child of the /chat request span"


@pytest.mark.static
def test_unguarded_chat_records_the_duration_metric(monkeypatch: pytest.MonkeyPatch, receiver: Received) -> None:
    """The dashboards' latency and 'answered unscanned' series come from gen_ai.client.operation.duration."""
    monkeypatch.delenv("BURRITBOT_GUARDED", raising=False)
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
    monkeypatch.setenv("BURRITBOT_DELIVERY", "summit-2027")
    monkeypatch.setenv("OTEL_SERVICE_NAME", "burritbot-unguarded")
    burritbot = _load("burritbot_app_telemetry_unguarded")
    assert _chat(burritbot, "recommend karaoke songs for a wedding") == 502

    span = _model_span(received=receiver, model=burritbot.MODEL_NAME)
    assert span.attributes["burritbot.guarded"] is False
    points = [p for p in receiver.points if p.metric == burritbot.OPERATION_DURATION]
    assert len(points) == 1, f"expected one {burritbot.OPERATION_DURATION} point, got {receiver.points}"
    point = points[0]
    assert point.unit == "s" and point.count == 1
    assert point.resource["service.name"] == "burritbot-unguarded"
    assert point.attributes == {
        "gen_ai.operation.name": "chat",
        "gen_ai.provider.name": "gcp.vertex_ai",
        "gen_ai.request.model": burritbot.MODEL_NAME,
        "burritbot.guarded": False,
        "error.type": "RuntimeError",
    }


@pytest.mark.static
def test_refusal_error_type_names_the_net(monkeypatch: pytest.MonkeyPatch) -> None:
    """A model call the net refused is error.type guardrails_refused, not an outage."""
    monkeypatch.delenv("BURRITBOT_GUARDED", raising=False)
    burritbot = _load("burritbot_app_telemetry_refusal")
    refused = burritbot.GuardrailsRefused(403, {"blocked_by": "llm-guard", "detail": "burritos only"})
    assert burritbot.model_call_error_type(refused) == "guardrails_refused"
    assert burritbot.model_call_error_type(RuntimeError("gateway down")) == "RuntimeError"


# --- live: the span and the metric reach Tempo and Prometheus ---------------


def _get_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=30) as resp:
        return json.loads(resp.read())


@pytest.mark.live
def test_live_unguarded_chat_reaches_tempo_and_prometheus(k8s_core_v1) -> None:
    """One audience prompt to unguarded BurritBot shows up as a span in Tempo and a series in Prometheus."""
    with port_forward("burritbot-unguarded", "burritbot-unguarded", 8080) as bot:
        req = urllib.request.Request(
            f"http://127.0.0.1:{bot}/chat",
            data=json.dumps({"prompt": "how do I throw a hot dog party"}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            assert resp.status == 200, f"unguarded /chat answered {resp.status}"
    # BatchSpanProcessor exports within 5s; the metric reader every 60s; the collector batches 5s more.
    deadline = time.monotonic() + 120
    traceql = '{ resource.service.name = "burritbot-unguarded" && span.gen_ai.operation.name = "chat" }'
    promql = 'burritbot_gen_ai_client_operation_duration_seconds_count{service_name="burritbot-unguarded"}'
    with (
        port_forward("monitoring", "tempo", 3100) as tempo,
        port_forward("monitoring", "prometheus-kube-prometheus-prometheus", 9090) as prom,
    ):
        while True:
            traces = _get_json(f"http://127.0.0.1:{tempo}/api/search?{urllib.parse.urlencode({'q': traceql})}")
            series = _get_json(f"http://127.0.0.1:{prom}/api/v1/query?{urllib.parse.urlencode({'query': promql})}")
            if traces.get("traces") and series["data"]["result"]:
                return
            assert time.monotonic() < deadline, (
                f"after 120s Tempo has {len(traces.get('traces') or [])} traces for {traceql} and Prometheus "
                f"{len(series['data']['result'])} series for {promql}"
            )
            time.sleep(10)
