# ABOUTME: Guarded traffic reaches the gateway routes it is meant to traverse (#67): the proxy
# ABOUTME: Service name, the audience Host header, and BurritBot's model call through the AIGatewayRoute.

from __future__ import annotations

import importlib.util
import re
import socket
import sys
from pathlib import Path
from types import ModuleType
from urllib.parse import urlsplit

import pytest
import yaml
from fastapi.testclient import TestClient

from conftest import PROJECT_ROOT, TERRAFORM_DIR


GATEWAY_FILE = PROJECT_ROOT / "ai-gateway" / "envoy" / "gateway.yaml"
BACKEND_FILE = PROJECT_ROOT / "ai-gateway" / "envoy" / "vertex-ai-backend.yaml"
FRONTEND_MAIN = PROJECT_ROOT / "apps" / "audience-frontend" / "backend" / "main.py"
FRONTEND_DEPLOYMENT = PROJECT_ROOT / "apps" / "audience-frontend" / "k8s" / "deployment.yaml"
BURRITBOT_APP = PROJECT_ROOT / "apps" / "burritbot" / "app.py"
GUARDED_DEPLOYMENT = PROJECT_ROOT / "apps" / "burritbot" / "k8s" / "deployment-guarded.yaml"
NETWORK_POLICY = PROJECT_ROOT / "security" / "kyverno" / "policies" / "restrict-burritbot-network.yaml"
IAM_TF = TERRAFORM_DIR / "iam.tf"

GATEWAY_NAMESPACE = "burritbot-net"
GATEWAY_NAME = "burritbot-ai-gateway"
AUDIENCE_ROUTE = "burritbot-audience"
AI_ROUTE = "burritbot-gemini-route"

# The OpenAI chat endpoint the AI Gateway router serves; its ext_proc reads
# the body's "model" into x-ai-eg-model, which the AIGatewayRoute matches.
OPENAI_CHAT_PATH = "/v1/chat/completions"

# Labels Envoy Gateway puts on every proxy pod it runs for a Gateway
# (internal/gatewayapi/resource/resource.go, v1.7.0).
OWNING_GATEWAY_NAME = "gateway.envoyproxy.io/owning-gateway-name"
OWNING_GATEWAY_NAMESPACE = "gateway.envoyproxy.io/owning-gateway-namespace"


def _docs(path: Path) -> list[dict]:
    return [d for d in yaml.safe_load_all(path.read_text(encoding="utf-8")) if d]


def _find(kind: str, name: str) -> dict:
    for path in (GATEWAY_FILE, BACKEND_FILE):
        for doc in _docs(path):
            if doc["kind"] == kind and doc["metadata"]["name"] == name:
                return doc
    raise AssertionError(f"{kind} {name} not found in ai-gateway/envoy/")


def _env(deployment: Path) -> dict[str, str]:
    container = _docs(deployment)[0]["spec"]["template"]["spec"]["containers"][0]
    return {e["name"]: e["value"] for e in container.get("env", []) if "value" in e}


def _proxy_namespace() -> str:
    """The namespace Envoy Gateway runs the proxy in, as the WIF binding names it."""
    match = re.search(r"svc\.id\.goog\[([^/\]]+)/" + GATEWAY_NAME + r"\]", IAM_TF.read_text())
    assert match, f"iam.tf has no WIF binding for the {GATEWAY_NAME} proxy KSA"
    return match.group(1)


def _listener_port() -> int:
    return _find("Gateway", GATEWAY_NAME)["spec"]["listeners"][0]["port"]


def _proxy_service_url() -> str:
    """The in-cluster URL of the Service Envoy Gateway creates for the gateway proxy."""
    gateway = _find("Gateway", GATEWAY_NAME)
    envoy_proxy = _find("EnvoyProxy", gateway["spec"]["infrastructure"]["parametersRef"]["name"])
    service = envoy_proxy["spec"]["provider"]["kubernetes"].get("envoyService", {})
    name = service.get("name")
    assert name, "EnvoyProxy does not pin envoyService.name; Envoy Gateway would hash the name"
    return f"http://{name}.{_proxy_namespace()}.svc.cluster.local:{_listener_port()}"


def _audience_hostnames() -> list[str]:
    return _find("HTTPRoute", AUDIENCE_ROUTE)["spec"].get("hostnames", [])


def _load(path: Path, name: str) -> ModuleType:
    """Import a fresh copy of a module, so it reads the environment as it is now."""
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader, f"cannot load {path}"
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _closed_port_url() -> str:
    """An http URL on a loopback port nothing listens on."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    return f"http://127.0.0.1:{port}"


# --- (1) the proxy Service has a name the callers can resolve -----------


@pytest.mark.static
def test_envoy_proxy_pins_a_cluster_ip_service_name() -> None:
    """The EnvoyProxy names the proxy Service and keeps it off an external load balancer."""
    envoy_proxy = _find("EnvoyProxy", GATEWAY_NAME)
    service = envoy_proxy["spec"]["provider"]["kubernetes"].get("envoyService", {})
    assert service.get("name") == GATEWAY_NAME, (
        f"EnvoyProxy envoyService.name is {service.get('name')!r}; without it the proxy "
        f"Service is envoy-{GATEWAY_NAMESPACE}-{GATEWAY_NAME}-<hash>"
    )
    assert service.get("type") == "ClusterIP", (
        f"EnvoyProxy envoyService.type is {service.get('type')!r}; Envoy Gateway's default "
        "LoadBalancer would expose the guarded gateway outside the cluster"
    )


@pytest.mark.static
def test_frontend_guarded_url_is_the_proxy_service() -> None:
    """The audience Deployment posts guarded traffic to the Service the EnvoyProxy names."""
    assert _env(FRONTEND_DEPLOYMENT)["BURRITBOT_GUARDED_URL"] == _proxy_service_url()


@pytest.mark.static
def test_frontend_guarded_url_default_is_the_proxy_service(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BURRITBOT_GUARDED_URL", raising=False)
    frontend = _load(FRONTEND_MAIN, "audience_frontend_main_guarded_url")
    assert frontend.BURRITBOT_GUARDED_URL == _proxy_service_url()


# --- (2) audience traffic carries the Host the audience route matches ---


@pytest.mark.static
def test_frontend_guarded_host_matches_the_audience_route() -> None:
    hostnames = _audience_hostnames()
    assert hostnames, f"HTTPRoute {AUDIENCE_ROUTE} has no hostnames"
    host = _env(FRONTEND_DEPLOYMENT).get("BURRITBOT_GUARDED_HOST")
    assert host in hostnames, (
        f"audience Deployment BURRITBOT_GUARDED_HOST is {host!r}; {AUDIENCE_ROUTE} matches {hostnames}"
    )


@pytest.mark.static
def test_frontend_sends_the_audience_host_on_the_guarded_target(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The guarded request names the audience hostname; the Service name would fall through."""
    monkeypatch.setenv("BURRITBOT_TARGET", "burritbot-guarded")
    monkeypatch.delenv("BURRITBOT_GUARDED_HOST", raising=False)
    frontend = _load(FRONTEND_MAIN, "audience_frontend_main_guarded_host")
    url, headers = frontend._resolve_target()
    assert url == frontend.BURRITBOT_GUARDED_URL
    assert headers.get("Host") in _audience_hostnames(), (
        f"guarded request Host is {headers.get('Host')!r}; {AUDIENCE_ROUTE} matches "
        f"{_audience_hostnames()}"
    )


@pytest.mark.static
def test_frontend_unguarded_target_keeps_its_own_host(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BURRITBOT_TARGET", "burritbot-unguarded")
    frontend = _load(FRONTEND_MAIN, "audience_frontend_main_unguarded_host")
    url, headers = frontend._resolve_target()
    assert url == frontend.BURRITBOT_UNGUARDED_URL
    assert "Host" not in headers


# --- (3) guarded BurritBot's model call goes through the AIGatewayRoute -


@pytest.mark.static
def test_ai_route_is_the_hostname_less_fallthrough() -> None:
    """The model call is told apart from audience traffic by Host alone."""
    route = _find("AIGatewayRoute", AI_ROUTE)
    assert not route["spec"].get("hostnames"), (
        f"{AI_ROUTE} sets hostnames; the guarded model call relies on it matching any Host"
    )


@pytest.mark.static
def test_guarded_deployment_calls_the_gateway() -> None:
    env = _env(GUARDED_DEPLOYMENT)
    assert env.get("AI_GATEWAY_URL") == _proxy_service_url(), (
        f"guarded BurritBot AI_GATEWAY_URL is {env.get('AI_GATEWAY_URL')!r}, "
        f"not the gateway proxy Service {_proxy_service_url()}"
    )
    host = urlsplit(env["AI_GATEWAY_URL"]).hostname
    assert host not in _audience_hostnames(), (
        f"AI_GATEWAY_URL host {host} matches {AUDIENCE_ROUTE}, which would loop the "
        "model call back into burritbot-guarded"
    )
    assert "GOOGLE_CLOUD_PROJECT" not in env, (
        "guarded BurritBot still carries GOOGLE_CLOUD_PROJECT; it never calls Vertex itself"
    )


@pytest.mark.static
def test_gateway_request_matches_the_ai_route(monkeypatch: pytest.MonkeyPatch) -> None:
    """BurritBot's gateway body carries the model the AIGatewayRoute matches, OpenAI-shaped."""
    monkeypatch.delenv("MODEL_NAME", raising=False)
    monkeypatch.delenv("BURRITBOT_GUARDED", raising=False)
    burritbot = _load(BURRITBOT_APP, "burritbot_app_gateway_body")
    assert burritbot.GATEWAY_CHAT_PATH == OPENAI_CHAT_PATH

    route = _find("AIGatewayRoute", AI_ROUTE)
    models = {
        h["value"]
        for rule in route["spec"]["rules"]
        for match in rule.get("matches", [])
        for h in match.get("headers", [])
        if h["name"] == "x-ai-eg-model"
    }
    body = burritbot.gateway_request_body("teach me some salsa dance moves")
    assert body["model"] in models, f"gateway body model {body['model']!r} matches none of {models}"
    assert body["messages"] == [
        {"role": "system", "content": burritbot.SYSTEM_PROMPT},
        {"role": "user", "content": "teach me some salsa dance moves"},
    ]


@pytest.mark.static
def test_gateway_response_is_read_from_the_openai_shape(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BURRITBOT_GUARDED", raising=False)
    burritbot = _load(BURRITBOT_APP, "burritbot_app_gateway_response")
    reply = burritbot.parse_gateway_response({
        "choices": [{"index": 0, "message": {"role": "assistant", "content": "Try the carnitas."}}],
        "usage": {"prompt_tokens": 42, "completion_tokens": 7, "total_tokens": 49},
    })
    assert reply == ("Try the carnitas.", 42, 7)
    with pytest.raises(ValueError, match="choices"):
        burritbot.parse_gateway_response({"choices": []})


@pytest.mark.static
def test_guarded_app_refuses_to_start_without_a_gateway(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BURRITBOT_GUARDED", "true")
    monkeypatch.delenv("AI_GATEWAY_URL", raising=False)
    with pytest.raises(RuntimeError, match="AI_GATEWAY_URL"):
        _load(BURRITBOT_APP, "burritbot_app_guarded_no_gateway")


@pytest.mark.static
def test_guarded_chat_goes_to_the_gateway_not_vertex(monkeypatch: pytest.MonkeyPatch) -> None:
    """With no Vertex project at all, a guarded /chat fails on the gateway hop, not on Vertex."""
    gateway_url = _closed_port_url()
    monkeypatch.setenv("BURRITBOT_GUARDED", "true")
    monkeypatch.setenv("AI_GATEWAY_URL", gateway_url)
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
    burritbot = _load(BURRITBOT_APP, "burritbot_app_guarded_chat")
    resp = TestClient(burritbot.app).post("/chat", json={"prompt": "how do I throw a hot dog party"})
    assert resp.status_code == 502, resp.text
    detail = resp.json()["detail"]
    assert "AI gateway" in detail and gateway_url in detail, detail
    assert "GOOGLE_CLOUD_PROJECT" not in detail, detail


@pytest.mark.static
def test_unguarded_chat_still_calls_vertex(monkeypatch: pytest.MonkeyPatch) -> None:
    """Act 1 is unchanged: unguarded BurritBot needs a Vertex project, not the gateway."""
    monkeypatch.delenv("BURRITBOT_GUARDED", raising=False)
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
    monkeypatch.setenv("BURRITBOT_DELIVERY", "summit-2027")
    burritbot = _load(BURRITBOT_APP, "burritbot_app_unguarded_chat")
    resp = TestClient(burritbot.app).post("/chat", json={"prompt": "recommend karaoke songs"})
    assert resp.status_code == 502, resp.text
    assert "GOOGLE_CLOUD_PROJECT is not set" in resp.json()["detail"]


# --- the guarded egress lock admits the proxy pods ----------------------


@pytest.mark.static
def test_guarded_egress_reaches_the_gateway_proxy_pods() -> None:
    """Envoy Gateway runs the proxy in its own namespace; the egress lock must admit those pods."""
    policy = _docs(NETWORK_POLICY)[0]
    egress = policy["spec"]["rules"][0]["generate"]["data"]["spec"]["egress"]
    proxy_rules = [
        rule
        for rule in egress
        for peer in rule.get("to", [])
        if peer.get("namespaceSelector", {}).get("matchLabels", {}).get("kubernetes.io/metadata.name")
        == _proxy_namespace()
        and peer.get("podSelector", {}).get("matchLabels", {})
        == {OWNING_GATEWAY_NAME: GATEWAY_NAME, OWNING_GATEWAY_NAMESPACE: GATEWAY_NAMESPACE}
    ]
    assert proxy_rules, (
        f"restrict-burritbot-network admits no egress to the {GATEWAY_NAME} proxy pods "
        f"in {_proxy_namespace()}"
    )
    ports = {p["port"] for rule in proxy_rules for p in rule.get("ports", [])}
    assert _listener_port() in ports, f"proxy egress ports {ports} miss the listener port"


# --- live --------------------------------------------------------------


@pytest.mark.live
def test_gateway_proxy_service_is_live(k8s_core_v1) -> None:
    """On the cluster, the proxy Service has the pinned name, namespace, type and port."""
    url = urlsplit(_proxy_service_url())
    name, namespace = url.hostname.split(".")[:2]
    svc = k8s_core_v1.read_namespaced_service(name=name, namespace=namespace)
    assert svc.spec.type == "ClusterIP", svc.spec.type
    assert url.port in {p.port for p in svc.spec.ports}, svc.spec.ports
