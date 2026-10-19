# ABOUTME: The guardrails ExtProc reaches a gRPC ext_proc server, not the scanners' REST ports (#66):
# ABOUTME: manifest wiring, the adapter's body and verdict contracts, a real in-process gRPC round trip, and live checks.

from __future__ import annotations

import asyncio
import copy
import gzip
import json
import re
import shutil
import socket
import subprocess
import sys
import time
import tomllib
from collections.abc import Iterator
from pathlib import Path

import pytest
import yaml
from opentelemetry.sdk.metrics import MeterProvider

from conftest import PROJECT_ROOT
from helpers.image_requirements import requirement_pins
from helpers.manifest_graph import kustomization_files
from helpers.otlp_receiver import otlp_receiver


EXTPROC_DIR = PROJECT_ROOT / "ai-gateway" / "extproc"
ADAPTER = EXTPROC_DIR / "adapter.py"
GATEWAY = PROJECT_ROOT / "ai-gateway" / "envoy" / "gateway.yaml"
DEPLOYMENTS = {
    "nemo-guardrails": PROJECT_ROOT / "ai-gateway" / "nemo-guardrails" / "deployment.yaml",
    "llm-guard": PROJECT_ROOT / "ai-gateway" / "llm-guard" / "deployment.yaml",
}
AI_GATEWAY_KUSTOMIZATION = PROJECT_ROOT / "deploy" / "ai-gateway" / "kustomization.yaml"
PYPROJECT = PROJECT_ROOT / "pyproject.toml"

SIDECAR = "burritbot-extproc"
# Config.from_env requires both; the refusal counter's exporter reads them.
OTEL_ENV = ("OTEL_EXPORTER_OTLP_ENDPOINT", "OTEL_SERVICE_NAME")
NAMESPACE = "burritbot-net"
# What the scanners themselves serve: REST, the NeMo microservice on 7331 (#90), llm-guard-api on 8000.
# Envoy's ext_proc there fails every request.
SCANNER_REST_PORTS = {"nemo-guardrails": 7331, "llm-guard": 8000}
ADAPTER_PINS = ("envoy-data-plane", "betterproto2", "grpclib", "httpx")


def _load_adapter():
    import importlib.util

    spec = importlib.util.spec_from_file_location("burritbot_extproc_adapter", ADAPTER)
    module = importlib.util.module_from_spec(spec)
    # dataclasses resolve string annotations through sys.modules.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


adapter = _load_adapter()


# --- manifest wiring --------------------------------------------------------


def _docs(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as fp:
        return [d for d in yaml.safe_load_all(fp) if d]


def _policy(gateway_docs: list[dict]) -> dict:
    found = [d for d in gateway_docs if d["kind"] == "EnvoyExtensionPolicy" and d["metadata"]["name"] == "burritbot-guardrails"]
    assert len(found) == 1, f"expected one burritbot-guardrails EnvoyExtensionPolicy, got {len(found)}"
    return found[0]


def _scanner_docs() -> list[dict]:
    return [d for path in DEPLOYMENTS.values() for d in _docs(path)]


def _container_behind(docs: list[dict], service: str, port: int) -> tuple[dict, int]:
    """The container a Service port forwards to, and its port, resolved from the Deployment it selects."""
    svcs = [d for d in docs if d["kind"] == "Service" and d["metadata"]["name"] == service]
    assert len(svcs) == 1, f"expected one Service {service}, got {len(svcs)}"
    svc = svcs[0]
    sp = [p for p in svc["spec"]["ports"] if p["port"] == port]
    assert sp, f"Service {service} exposes no port {port}"
    target = sp[0].get("targetPort", port)
    selector = svc["spec"]["selector"]
    for d in docs:
        if d["kind"] != "Deployment":
            continue
        labels = d["spec"]["template"]["metadata"].get("labels") or {}
        if any(labels.get(k) != v for k, v in selector.items()):
            continue
        for c in d["spec"]["template"]["spec"]["containers"]:
            for p in c.get("ports") or []:
                if (isinstance(target, str) and p.get("name") == target) or p.get("containerPort") == target:
                    return c, p["containerPort"]
    raise AssertionError(f"Service {service}:{port} targets {target!r}, which no selected container serves")


def _env(container: dict) -> dict[str, str]:
    return {e["name"]: e["value"] for e in container.get("env") or []}


def extproc_wiring_violations(policy: dict, docs: list[dict]) -> list[str]:
    """ExtProc backends that do not land on an ext_proc adapter for the scanner they name."""
    out: list[str] = []
    for i, ext in enumerate(policy["spec"]["extProc"]):
        for ref in ext["backendRefs"]:
            name, port = ref["name"], ref.get("port")
            container, container_port = _container_behind(docs, name, port)
            where = f"spec.extProc[{i}] {name}:{port}"
            if container["name"] != SIDECAR:
                out.append(f"{where} reaches container {container['name']!r}, not the {SIDECAR} gRPC adapter")
                continue
            if f"/{SIDECAR}:" not in container["image"]:
                out.append(f"{where} runs image {container['image']!r}, not the {SIDECAR} image")
            env = _env(container)
            if env.get("SCANNER") != name:
                out.append(f"{where} adapter is configured for SCANNER={env.get('SCANNER')!r}")
            if env.get("EXTPROC_PORT") != str(container_port):
                out.append(f"{where} adapter listens on EXTPROC_PORT={env.get('EXTPROC_PORT')!r}")
    return out


def _seconds(duration: str) -> float:
    match = re.fullmatch(r"(\d+(?:\.\d+)?)(ms|s|m)", duration)
    assert match, f"unparseable duration {duration!r}"
    value, unit = float(match.group(1)), match.group(2)
    return value * {"ms": 0.001, "s": 1, "m": 60}[unit]


def extproc_timeout_violations(policy: dict, docs: list[dict]) -> list[str]:
    """Entries that would fail or fail open before the adapter can answer."""
    out: list[str] = []
    for i, ext in enumerate(policy["spec"]["extProc"]):
        if ext.get("failOpen"):
            out.append(f"spec.extProc[{i}] failOpen lets unscanned traffic through")
        timeout = ext.get("messageTimeout")
        if timeout is None:
            out.append(f"spec.extProc[{i}] has no messageTimeout; Envoy's 200ms default fails every scan")
            continue
        for ref in ext["backendRefs"]:
            env = _env(_container_behind(docs, ref["name"], ref["port"])[0])
            if _seconds(timeout) <= float(env["SCANNER_TIMEOUT_SECONDS"]):
                out.append(
                    f"spec.extProc[{i}] messageTimeout {timeout} is not above {ref['name']}'s "
                    f"SCANNER_TIMEOUT_SECONDS {env['SCANNER_TIMEOUT_SECONDS']}"
                )
    return out


@pytest.mark.static
def test_extproc_backends_reach_the_adapter_not_the_rest_scanner() -> None:
    """#66: nemo-guardrails:7331 and llm-guard:8000 serve REST; Envoy needs envoy.service.ext_proc.v3."""
    violations = extproc_wiring_violations(_policy(_docs(GATEWAY)), _scanner_docs())
    assert not violations, "guardrails ExtProc wired to something that is not an ext_proc server:\n  " + "\n  ".join(violations)


@pytest.mark.static
@pytest.mark.parametrize("index", [0, 1])
def test_mutation_extproc_on_the_scanner_rest_port_is_caught(index: int) -> None:
    """The pre-#66 wiring: the ExtProc backend is the scanner's own REST port."""
    policy = copy.deepcopy(_policy(_docs(GATEWAY)))
    ref = policy["spec"]["extProc"][index]["backendRefs"][0]
    ref["port"] = SCANNER_REST_PORTS[ref["name"]]
    violations = extproc_wiring_violations(policy, _scanner_docs())
    assert any(f"spec.extProc[{index}]" in v and "not the burritbot-extproc gRPC adapter" in v for v in violations), violations


@pytest.mark.static
def test_mutation_adapter_for_the_other_scanner_is_caught() -> None:
    docs = copy.deepcopy(_scanner_docs())
    for d in docs:
        if d["kind"] == "Deployment" and d["metadata"]["name"] == "llm-guard":
            sidecar = next(c for c in d["spec"]["template"]["spec"]["containers"] if c["name"] == SIDECAR)
            next(e for e in sidecar["env"] if e["name"] == "SCANNER")["value"] = "nemo-guardrails"
    violations = extproc_wiring_violations(_policy(_docs(GATEWAY)), docs)
    assert any("llm-guard" in v and "SCANNER='nemo-guardrails'" in v for v in violations), violations


@pytest.mark.static
def test_extproc_timeouts_let_the_adapter_answer() -> None:
    violations = extproc_timeout_violations(_policy(_docs(GATEWAY)), _scanner_docs())
    assert not violations, "\n  ".join(violations)


@pytest.mark.static
@pytest.mark.parametrize(
    "mutate,expected",
    [
        (lambda ext: ext.pop("messageTimeout"), "200ms default"),
        (lambda ext: ext.update(messageTimeout="5s"), "is not above"),
        (lambda ext: ext.update(failOpen=True), "failOpen"),
    ],
    ids=["no-timeout", "timeout-under-adapter", "fail-open"],
)
def test_mutation_extproc_timeout_or_fail_open_is_caught(mutate, expected: str) -> None:
    policy = copy.deepcopy(_policy(_docs(GATEWAY)))
    mutate(policy["spec"]["extProc"][1])
    violations = extproc_timeout_violations(policy, _scanner_docs())
    assert any(expected in v for v in violations), violations


@pytest.mark.static
@pytest.mark.parametrize("scanner", sorted(DEPLOYMENTS))
def test_adapter_sidecar_is_complete(scanner: str) -> None:
    """Every variable Config.from_env requires is set, the scanner URL is the scanner's own port, names pass Kyverno."""
    docs = _docs(DEPLOYMENTS[scanner])
    deploy = next(d for d in docs if d["kind"] == "Deployment")
    containers = deploy["spec"]["template"]["spec"]["containers"]
    assert containers[0]["name"] == scanner, f"{scanner} is no longer the primary container"
    assert all(c["name"].startswith("burritbot-") for c in containers[1:]), (
        "require-burritbot-sidecar-naming refuses non-primary containers without the burritbot- prefix"
    )
    sidecar = next(c for c in containers if c["name"] == SIDECAR)
    env = _env(sidecar)
    required = {"SCANNER", "SCANNER_URL", "SCANNER_TIMEOUT_SECONDS", "EXTPROC_PORT", *OTEL_ENV}
    if scanner == adapter.NEMO:
        required |= {"NEMO_GUARDRAILS_MODEL", "NEMO_GUARDRAILS_CONFIG_ID"}
    assert required <= env.keys(), f"{scanner} adapter lacks {sorted(required - env.keys())}"
    scanner_ports = {p["containerPort"] for p in containers[0]["ports"]}
    assert env["SCANNER_URL"] in {f"http://127.0.0.1:{p}" for p in scanner_ports}, (
        f"{scanner} adapter calls {env['SCANNER_URL']}, the scanner serves {sorted(scanner_ports)}"
    )
    assert {p["containerPort"] for p in sidecar["ports"]} == {int(env["EXTPROC_PORT"])}
    security = sidecar["securityContext"]
    assert security["allowPrivilegeEscalation"] is False and security["readOnlyRootFilesystem"] is True


@pytest.mark.static
def test_adapter_image_pins_match_the_dev_group() -> None:
    """The image installs requirements.txt; the static tests below run on the dev group's copy."""
    pins = requirement_pins(EXTPROC_DIR / "requirements.txt")
    dev = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))["dependency-groups"]["dev"]
    dev_pins = {}
    for line in dev:
        name, sep, version = line.partition("==")
        if sep:
            dev_pins[name.lower()] = version
    for name in ADAPTER_PINS:
        assert pins.get(name), f"ai-gateway/extproc/requirements.txt has no exact pin for {name}"
        assert dev_pins.get(name) == pins[name], f"pyproject.toml pins {name} {dev_pins.get(name)}, the image {pins[name]}"


@pytest.mark.static
def test_adapter_dockerfile_runs_the_adapter_as_non_root() -> None:
    text = (EXTPROC_DIR / "Dockerfile").read_text(encoding="utf-8")
    assert "COPY --chown=burritbot:burritbot adapter.py /app/adapter.py" in text
    assert "USER burritbot:burritbot" in text and "--uid 1001" in text
    assert "EXPOSE 50051" in text
    assert 'CMD ["python", "/app/adapter.py"]' in text


@pytest.mark.static
def test_scanner_deployments_are_synced() -> None:
    """The sidecars ride in the scanner Deployments ArgoCD already syncs."""
    rendered = kustomization_files(PROJECT_ROOT, AI_GATEWAY_KUSTOMIZATION.parent)
    for path in DEPLOYMENTS.values():
        assert str(path.relative_to(PROJECT_ROOT)) in rendered


# --- the adapter's body contracts ------------------------------------------


@pytest.mark.static
def test_prompt_texts_reads_burritbot_and_openai_requests() -> None:
    assert adapter.prompt_texts(b'{"prompt": "teach me some salsa dance moves"}') == [
        (("prompt",), "teach me some salsa dance moves")
    ]
    openai = {
        "model": "gemini-3-pro",
        "messages": [
            {"role": "system", "content": "You are BurritBot."},
            {"role": "user", "content": "how do I throw a hot dog party"},
            {"role": "assistant", "content": "Let's talk burritos."},
            {"role": "user", "content": [{"type": "text", "text": "karaoke songs?"}, {"type": "image_url"}]},
        ],
    }
    assert adapter.prompt_texts(json.dumps(openai).encode()) == [
        (("messages", 1, "content"), "how do I throw a hot dog party"),
        (("messages", 3, "content", 0, "text"), "karaoke songs?"),
    ]


@pytest.mark.static
@pytest.mark.parametrize(
    "body",
    [b"prompt=salsa", b"\xff\xfe", b"[]", b'{"messages": [{"role": "system", "content": "x"}]}', b'{"text": "salsa"}'],
    ids=["form", "binary", "list", "no-user-message", "unknown-field"],
)
def test_prompt_texts_refuses_bodies_it_cannot_read(body: bytes) -> None:
    with pytest.raises(adapter.UnreadableBody):
        adapter.prompt_texts(body)


@pytest.mark.static
def test_output_texts_reads_replies_and_skips_bodies_without_model_text() -> None:
    assert adapter.output_texts(b'{"reply": "Try the barbacoa.", "guarded": true}') == [(("reply",), "Try the barbacoa.")]
    choices = {"choices": [{"message": {"role": "assistant", "content": "Burritos only."}}]}
    assert adapter.output_texts(json.dumps(choices).encode()) == [(("choices", 0, "message", "content"), "Burritos only.")]
    assert adapter.output_texts(b'{"status": "ok", "model": "gemini-3-pro", "guarded": true}') == []
    assert adapter.output_texts(b"upstream connect error") == []


@pytest.mark.static
def test_replace_texts_rewrites_only_the_named_fields() -> None:
    body = json.dumps({"model": "m", "messages": [{"role": "user", "content": "mail me at a@b.co"}]}).encode()
    out = json.loads(adapter.replace_texts(body, [(("messages", 0, "content"), "mail me at [REDACTED_EMAIL_ADDRESS_1]")]))
    assert out == {"model": "m", "messages": [{"role": "user", "content": "mail me at [REDACTED_EMAIL_ADDRESS_1]"}]}


# --- the scanners' REST contracts ------------------------------------------


@pytest.mark.static
def test_llm_guard_verdicts() -> None:
    allowed = adapter.llm_guard_verdict(
        {"is_valid": True, "scanners": {"BanTopics": 0.1}, "sanitized_prompt": "a burrito please"}, "sanitized_prompt"
    )
    assert allowed == adapter.Verdict(True, "a burrito please", {"BanTopics": 0.1})
    blocked = adapter.llm_guard_verdict(
        {"is_valid": False, "scanners": {"BanTopics": 0.97}, "sanitized_output": "salsa steps"}, "sanitized_output"
    )
    assert not blocked.allowed and blocked.findings == {"BanTopics": 0.97}


@pytest.mark.static
@pytest.mark.parametrize(
    "reply",
    [None, {"is_valid": "false", "scanners": {}, "sanitized_prompt": ""}, {"is_valid": True, "scanners": {}}, {"detail": "Unauthorized"}],
)
def test_llm_guard_reply_out_of_contract_is_a_scanner_error(reply: object) -> None:
    with pytest.raises(adapter.ScannerError):
        adapter.llm_guard_verdict(reply, "sanitized_prompt")


@pytest.mark.static
def test_nemo_checks_payload_and_verdicts() -> None:
    assert adapter.nemo_checks_payload("gemini-3-pro", "burritbot", "salsa?") == {
        "model": "gemini-3-pro",
        "messages": [{"role": "user", "content": "salsa?"}],
        "guardrails": {"config_id": "burritbot"},
    }
    output = adapter.nemo_checks_payload("gemini-3-pro", "burritbot", "salsa?", "Step left...")
    assert output["messages"][1] == {"role": "assistant", "content": "Step left..."}
    blocked = adapter.nemo_verdict(
        {"status": "blocked", "rails_status": {"burrito only input": {"status": "blocked"}}}, "salsa?"
    )
    assert blocked == adapter.Verdict(False, "salsa?", {"burrito only input": {"status": "blocked"}})
    assert adapter.nemo_verdict({"status": "success", "rails_status": {}}, "a burrito").allowed


@pytest.mark.static
@pytest.mark.parametrize("reply", [{"status": "error", "rails_status": {}}, {"status": "success"}, ["blocked"]])
def test_nemo_reply_out_of_contract_is_a_scanner_error(reply: object) -> None:
    with pytest.raises(adapter.ScannerError):
        adapter.nemo_verdict(reply, "salsa?")


@pytest.mark.static
@pytest.mark.parametrize(
    "missing",
    [
        "SCANNER",
        "SCANNER_URL",
        "SCANNER_TIMEOUT_SECONDS",
        "EXTPROC_PORT",
        "NEMO_GUARDRAILS_MODEL",
        "NEMO_GUARDRAILS_CONFIG_ID",
        *OTEL_ENV,
    ],
)
def test_config_fails_without_each_variable(monkeypatch: pytest.MonkeyPatch, missing: str) -> None:
    env = {
        "SCANNER": "nemo-guardrails",
        "SCANNER_URL": "http://127.0.0.1:7331",
        "SCANNER_TIMEOUT_SECONDS": "8",
        "EXTPROC_PORT": "50051",
        "NEMO_GUARDRAILS_MODEL": "gemini-3-pro",
        "NEMO_GUARDRAILS_CONFIG_ID": "burritbot",
        "OTEL_EXPORTER_OTLP_ENDPOINT": "http://otel-collector.monitoring.svc.cluster.local:4317",
        "OTEL_SERVICE_NAME": "burritbot-extproc-nemo-guardrails",
    }
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    assert adapter.Config.from_env().nemo_config_id == "burritbot"
    monkeypatch.delenv(missing)
    with pytest.raises(RuntimeError, match=missing):
        adapter.Config.from_env()


# --- a real gRPC round trip against the adapter -----------------------------
#
# The adapter's server and Envoy's protocol messages are real; the scanner is
# a localhost port nothing listens on, which is exactly the outage the net
# must refuse traffic through.


def _closed_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _round_trip(
    requests: list, scanner: str = "llm-guard", scanner_port: int | None = None, provider: MeterProvider | None = None
) -> list:
    from envoy_data_plane.envoy.service.ext_proc.v3 import ExternalProcessorAsyncStub
    from grpclib.client import Channel
    from grpclib.server import Server

    config = adapter.Config(
        scanner=scanner,
        scanner_url=f"http://127.0.0.1:{scanner_port or _closed_port()}",
        timeout_seconds=2.0,
        port=0,
        nemo_model="gemini-3-pro",
        nemo_config_id="burritbot",
    )

    async def run() -> list:
        async with config.http_client() as client:
            meter = (provider or adapter.meter_provider()).get_meter("burritbot-extproc")
            server = Server([adapter.GuardrailsProcessor(config.scanner_for(client), meter)])
            port = _closed_port()
            await server.start("127.0.0.1", port)
            channel = Channel("127.0.0.1", port)
            try:
                stub = ExternalProcessorAsyncStub(channel)
                return [r async for r in stub.process(requests, timeout=10)]
            finally:
                channel.close()
                server.close()
                await server.wait_closed()

    return asyncio.run(run())


def _headers():
    from envoy_data_plane.envoy.config.core.v3 import HeaderMap, HeaderValue
    from envoy_data_plane.envoy.service.ext_proc.v3 import HttpHeaders

    return HttpHeaders(headers=HeaderMap(headers=[HeaderValue(key=":path", raw_value=b"/chat")]))


def _body(data: bytes):
    from envoy_data_plane.envoy.service.ext_proc.v3 import HttpBody

    return HttpBody(body=data, end_of_stream=True)


@pytest.mark.static
@pytest.mark.parametrize("scanner", ["llm-guard", "nemo-guardrails"])
def test_round_trip_scanner_down_refuses_with_503(scanner: str) -> None:
    from envoy_data_plane.envoy.service.ext_proc.v3 import ProcessingRequest

    responses = _round_trip(
        [
            ProcessingRequest(request_headers=_headers()),
            ProcessingRequest(request_body=_body(b'{"prompt": "teach me some salsa dance moves"}')),
        ],
        scanner=scanner,
    )
    assert responses[0].request_headers is not None, "headers must be let through to reach the body"
    refused = responses[1].immediate_response
    assert refused is not None, f"scanner outage let the prompt through: {responses[1]!r}"
    assert refused.status.code == 503
    assert json.loads(refused.body)["blocked_by"] == scanner


@pytest.mark.static
def test_round_trip_refusal_is_counted_and_exported(monkeypatch: pytest.MonkeyPatch) -> None:
    """The refusal reaches a real OTLP receiver as burritbot.guardrails.refusals, labelled for the dashboard (#101)."""
    from envoy_data_plane.envoy.service.ext_proc.v3 import ProcessingRequest

    with otlp_receiver() as (endpoint, received):
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", endpoint)
        monkeypatch.setenv("OTEL_SERVICE_NAME", "burritbot-extproc-llm-guard")
        provider = adapter.meter_provider()
        responses = _round_trip(
            [ProcessingRequest(request_body=_body(b'{"prompt": "teach me some salsa dance moves"}'))],
            provider=provider,
        )
        assert responses[0].immediate_response is not None
        assert provider.force_flush(), "the adapter could not export to the OTLP receiver"
    points = [p for p in received.points if p.metric == adapter.REFUSALS]
    assert len(points) == 1, f"expected one {adapter.REFUSALS} point, got {received.points}"
    assert points[0].value == 1
    assert points[0].resource["service.name"] == "burritbot-extproc-llm-guard"
    assert points[0].attributes == {
        "burritbot.scanner": "llm-guard",
        "burritbot.direction": "prompt",
        "http.response.status_code": 503,
    }


@pytest.mark.static
def test_passed_exchanges_are_not_counted() -> None:
    """Only refusals count: a reply with no model text passes and leaves the counter untouched."""
    from envoy_data_plane.envoy.service.ext_proc.v3 import ProcessingRequest
    from opentelemetry.sdk.metrics.export import InMemoryMetricReader

    reader = InMemoryMetricReader()
    _round_trip(
        [ProcessingRequest(response_body=_body(b'{"status": "ok"}'))],
        provider=MeterProvider(metric_readers=[reader]),
    )
    assert reader.get_metrics_data() is None or not reader.get_metrics_data().resource_metrics


@pytest.mark.static
def test_round_trip_unreadable_body_refuses_with_400() -> None:
    from envoy_data_plane.envoy.service.ext_proc.v3 import ProcessingRequest

    responses = _round_trip([ProcessingRequest(request_body=_body(b"prompt=salsa"))])
    assert responses[0].immediate_response is not None
    assert responses[0].immediate_response.status.code == 400


@pytest.mark.static
def test_round_trip_reply_without_model_text_passes() -> None:
    """A health check through the gateway carries no model output; nothing to scan, nothing called."""
    from envoy_data_plane.envoy.service.ext_proc.v3 import ProcessingRequest

    responses = _round_trip(
        [
            ProcessingRequest(response_headers=_headers()),
            ProcessingRequest(response_body=_body(b'{"status": "ok", "model": "gemini-3-pro", "guarded": true}')),
        ]
    )
    assert responses[0].response_headers is not None
    passed = responses[1].response_body
    assert passed is not None and passed.response.body_mutation is None


# --- the model hop (#94) ------------------------------------------------------
#
# The policy targets the Gateway, so the net also runs on guarded BurritBot's
# model call. There the AI Gateway's own ext_proc sits ahead of the net
# (insertAIGatewayExtProcFilter, v0.6.0 to v1.2.0). It reads the OpenAI request
# before the net does and translates that copy for Vertex, and it translates
# Vertex's reply to OpenAI only after the net has seen it.

VERTEX_REPLY = {
    "candidates": [
        {
            "content": {"role": "model", "parts": [{"text": "Step left, then right."}, {"thoughtSignature": "c2ln"}]},
            "finishReason": "STOP",
        }
    ],
    "usageMetadata": {"promptTokenCount": 40, "candidatesTokenCount": 6},
}


@pytest.mark.static
def test_output_texts_reads_the_vertex_reply_on_the_model_hop() -> None:
    assert adapter.output_texts(json.dumps(VERTEX_REPLY).encode()) == [
        (("candidates", 0, "content", "parts", 0, "text"), "Step left, then right.")
    ]


@pytest.mark.static
@pytest.mark.parametrize("scanner", ["llm-guard", "nemo-guardrails"])
def test_round_trip_vertex_reply_is_scanned(scanner: str) -> None:
    """Vertex's reply reaches the scanner: with the scanner down it is refused, never passed unscanned."""
    from envoy_data_plane.envoy.service.ext_proc.v3 import ProcessingRequest

    responses = _round_trip(
        [
            ProcessingRequest(response_headers=_headers()),
            ProcessingRequest(response_body=_body(json.dumps(VERTEX_REPLY).encode())),
        ],
        scanner=scanner,
    )
    refused = responses[1].immediate_response
    assert refused is not None, f"Vertex's reply passed unscanned: {responses[1]!r}"
    assert refused.status.code == 503
    assert json.loads(refused.body)["blocked_by"] == scanner


def _encoded_headers(encoding: str):
    from envoy_data_plane.envoy.config.core.v3 import HeaderMap, HeaderValue
    from envoy_data_plane.envoy.service.ext_proc.v3 import HttpHeaders

    return HttpHeaders(
        headers=HeaderMap(
            headers=[
                HeaderValue(key=":status", raw_value=b"200"),
                HeaderValue(key="content-encoding", raw_value=encoding.encode()),
            ]
        )
    )


@pytest.mark.static
def test_round_trip_encoded_reply_is_refused() -> None:
    """A compressed reply cannot be read, so it is refused rather than passed unscanned."""
    from envoy_data_plane.envoy.service.ext_proc.v3 import ProcessingRequest

    responses = _round_trip(
        [
            ProcessingRequest(response_headers=_encoded_headers("gzip")),
            ProcessingRequest(response_body=_body(gzip.compress(json.dumps(VERTEX_REPLY).encode()))),
        ]
    )
    refused = responses[1].immediate_response
    assert refused is not None, f"a gzip reply passed unscanned: {responses[1]!r}"
    assert refused.status.code == 502
    assert json.loads(refused.body)["blocked_by"] == "llm-guard"


@pytest.mark.static
def test_content_encoding_is_read_from_the_response_headers() -> None:
    assert adapter.content_encoding(_encoded_headers("GZIP")) == "gzip"
    assert adapter.content_encoding(_headers()) == ""


@pytest.mark.static
def test_sanitized_openai_prompt_is_refused_not_forwarded() -> None:
    """The gateway would send the unsanitized original to Vertex, so the net refuses instead."""
    body = json.dumps({"model": "gemini-3-pro", "messages": [{"role": "user", "content": "mail a@b.co"}]}).encode()
    response = adapter.scanned_body("llm-guard", True, body, [(("messages", 0, "content"), "mail [REDACTED]")])
    refused = response.immediate_response
    assert refused is not None, f"a rewrite the gateway drops was forwarded: {response!r}"
    assert refused.status.code == 403
    assert json.loads(refused.body)["blocked_by"] == "llm-guard"


@pytest.mark.static
@pytest.mark.parametrize(
    ("request_side", "body", "path"),
    [
        (True, {"prompt": "mail a@b.co"}, ("prompt",)),
        (False, VERTEX_REPLY, ("candidates", 0, "content", "parts", 0, "text")),
        (False, {"reply": "mail a@b.co"}, ("reply",)),
    ],
    ids=["audience-prompt", "vertex-reply", "audience-reply"],
)
def test_sanitized_text_that_reaches_its_reader_is_rewritten(request_side: bool, body: dict, path: tuple) -> None:
    response = adapter.scanned_body("llm-guard", request_side, json.dumps(body).encode(), [(path, "[REDACTED]")])
    passed = response.request_body if request_side else response.response_body
    assert passed is not None, f"expected the rewritten body to pass: {response!r}"
    node = json.loads(passed.response.body_mutation.body)
    for key in path:
        node = node[key]
    assert node == "[REDACTED]"


# --- live: the adapters run and the net bites on the cluster ----------------


@pytest.mark.live
@pytest.mark.parametrize("scanner", sorted(DEPLOYMENTS))
def test_adapter_sidecar_ready(k8s_core_v1, scanner: str) -> None:
    pods = k8s_core_v1.list_namespaced_pod(namespace=NAMESPACE, label_selector=f"app.kubernetes.io/name={scanner}").items
    assert pods, f"no {scanner} pods in {NAMESPACE}"
    for pod in pods:
        statuses = {s.name: s for s in pod.status.container_statuses or []}
        assert SIDECAR in statuses, f"{pod.metadata.name} runs no {SIDECAR} container"
        assert statuses[SIDECAR].ready, f"{pod.metadata.name} {SIDECAR} is not ready"


@pytest.fixture
def forwarded_extproc(request) -> Iterator[int]:
    """kubectl port-forward to the scanner Service's extproc port. Needs kubectl and the cluster."""
    kubectl = shutil.which("kubectl")
    assert kubectl, "kubectl is not on PATH; the live ext_proc check port-forwards with it"
    local = _closed_port()
    proc = subprocess.Popen(
        [kubectl, "-n", NAMESPACE, "port-forward", f"svc/{request.param}", f"{local}:50051"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    try:
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            assert proc.poll() is None, f"port-forward exited: {proc.stdout.read().decode()}"
            with socket.socket() as s:
                if s.connect_ex(("127.0.0.1", local)) == 0:
                    break
            time.sleep(0.5)
        else:
            raise AssertionError(f"port-forward to svc/{request.param}:50051 never opened")
        yield local
    finally:
        proc.terminate()
        proc.wait(timeout=10)


@pytest.mark.live
@pytest.mark.parametrize("forwarded_extproc", sorted(DEPLOYMENTS), indirect=True)
def test_live_adapter_blocks_the_act_1_prompt(forwarded_extproc: int) -> None:
    """The canonical Act 1 prompt, sent as Envoy would, comes back refused with a 403."""
    from envoy_data_plane.envoy.service.ext_proc.v3 import (
        ExternalProcessorAsyncStub,
        ProcessingRequest,
    )
    from grpclib.client import Channel

    async def run() -> list:
        channel = Channel("127.0.0.1", forwarded_extproc)
        try:
            stub = ExternalProcessorAsyncStub(channel)
            requests = [
                ProcessingRequest(request_headers=_headers()),
                ProcessingRequest(request_body=_body(b'{"prompt": "teach me some salsa dance moves"}')),
            ]
            return [r async for r in stub.process(requests, timeout=30)]
        finally:
            channel.close()

    responses = asyncio.run(run())
    refused = responses[1].immediate_response
    assert refused is not None, f"the Act 1 prompt was let through: {responses[1]!r}"
    assert refused.status.code == 403, f"expected a guardrails 403, got {refused.status.code}: {refused.body!r}"
