# ABOUTME: The controllers behind gateway.yaml are installed (#68): Envoy Gateway, the AI Gateway CRDs and
# ABOUTME: controller as pinned ArgoCD Applications, the envoy-ai-gateway GatewayClass, and their sync order.

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlsplit

import pytest
import yaml

from conftest import PROJECT_ROOT, TERRAFORM_DIR
from helpers.manifest_graph import kustomized_paths, load_manifests


GITOPS_APPS = PROJECT_ROOT / "gitops" / "apps"
NAMESPACES_FILE = PROJECT_ROOT / "gitops" / "namespaces" / "namespaces.yaml"
EG_APP = GITOPS_APPS / "envoy-gateway.yaml"
AIGW_CRDS_APP = GITOPS_APPS / "ai-gateway-crds.yaml"
AIGW_CONTROLLER_APP = GITOPS_APPS / "ai-gateway-controller.yaml"
AI_GATEWAY_APP = GITOPS_APPS / "20-ai-gateway.yaml"
NAMESPACES_APP = GITOPS_APPS / "00-namespaces.yaml"
CERT_MANAGER_APP = GITOPS_APPS / "cert-manager.yaml"
GATEWAYCLASS_FILE = PROJECT_ROOT / "ai-gateway" / "envoy" / "gatewayclass.yaml"
GUARDED_DEPLOYMENT = PROJECT_ROOT / "apps" / "burritbot" / "k8s" / "deployment-guarded.yaml"
IAM_TF = TERRAFORM_DIR / "iam.tf"

# Docker Hub OCI repository both projects publish their charts to.
CHART_REPO = "docker.io/envoyproxy"
# Agent Router (formerly Envoy AI Gateway) v1.2.0 builds against Envoy Gateway
# v1.9.2; decision #53 checked gateway.yaml against both.
EG_CHART = ("gateway-helm", "v1.9.2")
AIGW_CRDS_CHART = ("ai-gateway-crds-helm", "v1.2.0")
AIGW_CONTROLLER_CHART = ("ai-gateway-helm", "v1.2.0")

GATEWAYCLASS_NAME = "envoy-ai-gateway"
GATEWAY_NAME = "burritbot-ai-gateway"

# The AI Gateway controller's extension server port (ai-gateway-helm
# controller.service.ports "grpc").
EXTENSION_SERVER_PORT = 1063

# Ports the GKE control plane may open to pods on a private-node cluster
# peered by VPC Network Peering: the auto-created "-master" firewall rule
# allows TCP 443 and 10250 only. A webhook on any other port times out.
GKE_CONTROL_PLANE_PORTS = {443, 10250}


def _docs(path: Path) -> list[dict]:
    return [d for d in yaml.safe_load_all(path.read_text(encoding="utf-8")) if d]


def _app(path: Path) -> dict:
    assert path.is_file(), f"missing {path.relative_to(PROJECT_ROOT)}"
    apps = [d for d in _docs(path) if d.get("kind") == "Application"]
    assert len(apps) == 1, f"{path.name}: expected one Application, found {len(apps)}"
    return apps[0]


def _wave(path: Path) -> int:
    return int(_app(path)["metadata"]["annotations"]["argocd.argoproj.io/sync-wave"])


def _values(path: Path) -> dict:
    return _app(path)["spec"]["source"]["helm"]["valuesObject"]


def _sync_options(path: Path) -> list[str]:
    return _app(path)["spec"]["syncPolicy"].get("syncOptions", [])


def _eg_config() -> dict:
    return _values(EG_APP)["config"]["envoyGateway"]


def _controller() -> dict:
    return _values(AIGW_CONTROLLER_APP)["controller"]


def _declared_namespaces() -> set[str]:
    return {d["metadata"]["name"] for d in _docs(NAMESPACES_FILE) if d.get("kind") == "Namespace"}


# --- the three Applications --------------------------------------------------


@pytest.mark.static
@pytest.mark.parametrize(
    "path,chart",
    [(EG_APP, EG_CHART), (AIGW_CRDS_APP, AIGW_CRDS_CHART), (AIGW_CONTROLLER_APP, AIGW_CONTROLLER_CHART)],
    ids=lambda x: x.name if isinstance(x, Path) else x[0],
)
def test_chart_is_pinned(path: Path, chart: tuple[str, str]) -> None:
    source = _app(path)["spec"]["source"]
    assert (source.get("repoURL"), source.get("chart"), source.get("targetRevision")) == (CHART_REPO, *chart)


@pytest.mark.static
def test_crds_and_controller_are_the_same_release() -> None:
    crds = _app(AIGW_CRDS_APP)["spec"]["source"]["targetRevision"]
    controller = _app(AIGW_CONTROLLER_APP)["spec"]["source"]["targetRevision"]
    assert crds == controller, f"AI Gateway CRDs {crds} and controller {controller} must move together"


@pytest.mark.static
@pytest.mark.parametrize("path", [EG_APP, AIGW_CRDS_APP], ids=lambda p: p.name)
def test_crd_apps_apply_server_side(path: Path) -> None:
    """The Gateway API and EnvoyProxy CRDs exceed the 256 KiB last-applied
    annotation that client-side apply writes; ArgoCD must apply them server-side."""
    assert "ServerSideApply=true" in _sync_options(path)


@pytest.mark.static
def test_crds_chart_installs_no_gateway_api_crds() -> None:
    """Envoy Gateway's chart already carries the Gateway API CRDs; the AI
    Gateway CRD chart carries only aigateway.envoyproxy.io."""
    values = _app(AIGW_CRDS_APP)["spec"]["source"].get("helm", {}).get("valuesObject", {})
    assert not values, f"ai-gateway-crds-helm takes no values; found {values}"


@pytest.mark.static
@pytest.mark.parametrize("path", [EG_APP, AIGW_CRDS_APP, AIGW_CONTROLLER_APP], ids=lambda p: p.name)
def test_destination_namespace_is_declared(path: Path) -> None:
    namespace = _app(path)["spec"]["destination"]["namespace"]
    assert namespace in _declared_namespaces(), f"{namespace} is not in {NAMESPACES_FILE.name}"
    assert "CreateNamespace=false" in _sync_options(path)


@pytest.mark.static
def test_envoy_gateway_runs_where_the_proxy_is_called() -> None:
    """Envoy Gateway runs each proxy in its own namespace. The WIF binding, the
    guarded AI_GATEWAY_URL and the AI Gateway controller all name that namespace."""
    eg_namespace = _app(EG_APP)["spec"]["destination"]["namespace"]

    wif = re.search(r"svc\.id\.goog\[([^/\]]+)/" + GATEWAY_NAME + r"\]", IAM_TF.read_text(encoding="utf-8"))
    assert wif, f"no WIF binding for {GATEWAY_NAME} in {IAM_TF.name}"
    assert wif.group(1) == eg_namespace

    container = _docs(GUARDED_DEPLOYMENT)[0]["spec"]["template"]["spec"]["containers"][0]
    url = next(e["value"] for e in container["env"] if e["name"] == "AI_GATEWAY_URL")
    assert urlsplit(url).hostname == f"{GATEWAY_NAME}.{eg_namespace}.svc.cluster.local"

    assert _values(AIGW_CONTROLLER_APP)["envoyGateway"]["namespace"] == eg_namespace


# --- Envoy Gateway is configured for the AI Gateway ----------------------------


@pytest.mark.static
def test_extension_manager_calls_the_ai_gateway_controller() -> None:
    controller_namespace = _app(AIGW_CONTROLLER_APP)["spec"]["destination"]["namespace"]
    service = _eg_config()["extensionManager"]["service"]["fqdn"]
    assert service == {
        "hostname": f"{_controller()['fullnameOverride']}.{controller_namespace}.svc.cluster.local",
        "port": EXTENSION_SERVER_PORT,
    }


@pytest.mark.static
def test_extension_manager_hooks_match_upstream() -> None:
    """manifests/envoy-gateway-values.yaml at Agent Router v1.2.0."""
    translator = _eg_config()["extensionManager"]["hooks"]["xdsTranslator"]
    assert translator["post"] == ["Translation", "Cluster", "Route"]
    for kind in ("listener", "route", "cluster", "secret"):
        assert translator["translation"][kind] == {"includeAll": True}, kind


@pytest.mark.static
def test_backend_api_is_enabled() -> None:
    """vertex-ai-backend.yaml uses the gateway.envoyproxy.io Backend kind,
    which Envoy Gateway serves only with enableBackend."""
    uses_backend = any(
        m.group == "gateway.envoyproxy.io" and m.kind == "Backend" for m in load_manifests(PROJECT_ROOT)
    )
    assert uses_backend, "no Backend manifest found; the check below would prove nothing"
    assert _eg_config()["extensionApis"]["enableBackend"] is True


# --- the GatewayClass -----------------------------------------------------------


def _gatewayclasses() -> dict[str, dict]:
    return {
        m.name: m.doc
        for m in load_manifests(PROJECT_ROOT)
        if m.group == "gateway.networking.k8s.io" and m.kind == "GatewayClass"
    }


@pytest.mark.static
def test_every_gateway_names_a_defined_gatewayclass() -> None:
    classes = _gatewayclasses()
    gateways = [
        m for m in load_manifests(PROJECT_ROOT) if m.group == "gateway.networking.k8s.io" and m.kind == "Gateway"
    ]
    assert gateways, "no Gateway found; the check below would prove nothing"
    missing = [m.label for m in gateways if m.doc["spec"]["gatewayClassName"] not in classes]
    assert not missing, f"Gateways naming no GatewayClass in the repo: {missing}"


@pytest.mark.static
def test_gatewayclass_is_owned_by_envoy_gateway() -> None:
    gatewayclass = _gatewayclasses().get(GATEWAYCLASS_NAME)
    assert gatewayclass, f"GatewayClass {GATEWAYCLASS_NAME} not defined"
    assert gatewayclass["spec"]["controllerName"] == _eg_config()["gateway"]["controllerName"]


@pytest.mark.static
def test_gatewayclass_is_synced() -> None:
    synced = kustomized_paths(PROJECT_ROOT, load_manifests(PROJECT_ROOT))
    assert str(GATEWAYCLASS_FILE.relative_to(PROJECT_ROOT)) in synced


# --- the AI Gateway controller renders stably under ArgoCD ----------------------


@pytest.mark.static
def test_webhook_cert_comes_from_cert_manager() -> None:
    """ArgoCD renders with helm template, where lookup returns nothing: the
    chart's own genCA path would mint a new webhook keypair on every render."""
    assert _controller()["mutatingWebhook"]["certManager"]["enable"] is True


@pytest.mark.static
def test_webhook_port_is_open_to_the_gke_control_plane() -> None:
    controller = _controller()
    port = controller["mutatingWebhook"]["port"]
    assert port in GKE_CONTROL_PLANE_PORTS, f"webhook port {port} is closed to the GKE control plane"
    service = {p["name"]: p for p in controller["service"]["ports"]}
    assert service["mutating-webhook"]["port"] == port
    assert service["mutating-webhook"]["targetPort"] == port
    assert service["grpc"]["port"] == EXTENSION_SERVER_PORT


@pytest.mark.static
def test_envoy_gateway_topology_webhook_is_off() -> None:
    """Its webhook listens on 9443, which the GKE control plane cannot reach."""
    assert _values(EG_APP)["topologyInjector"]["enabled"] is False


@pytest.mark.static
def test_mcp_session_seed_is_not_regenerated_or_committed() -> None:
    """Without lookup the chart draws a fresh random seed on every render.
    The live Secret keeps the first one; no seed is written into Git."""
    encryption = _controller().get("mcp", {}).get("sessionEncryption", {})
    assert not encryption.get("seed"), "an MCP session seed in Git is a committed secret"
    assert not encryption.get("existingSecret")

    app = _app(AIGW_CONTROLLER_APP)
    secret = f"{_controller()['fullnameOverride']}-mcp-session-encryption"
    ignored = [
        d
        for d in app["spec"].get("ignoreDifferences", [])
        if d.get("kind") == "Secret" and d.get("name") == secret
    ]
    assert ignored and "/data/seed" in ignored[0].get("jsonPointers", []), f"Secret {secret} seed is not ignored"
    assert "RespectIgnoreDifferences=true" in _sync_options(AIGW_CONTROLLER_APP)


# --- sync order -------------------------------------------------------------------


@pytest.mark.static
def test_controllers_sync_before_the_gateway_resources() -> None:
    gateway = _wave(AI_GATEWAY_APP)
    assert _wave(NAMESPACES_APP) < _wave(EG_APP) < gateway
    assert _wave(NAMESPACES_APP) < _wave(AIGW_CRDS_APP) < gateway
    assert _wave(CERT_MANAGER_APP) < _wave(AIGW_CONTROLLER_APP) < gateway
    assert _wave(EG_APP) <= _wave(AIGW_CONTROLLER_APP)


# --- live -------------------------------------------------------------------------


@pytest.mark.live
@pytest.mark.parametrize(
    "crd",
    [
        "aigatewayroutes.aigateway.envoyproxy.io",
        "aiservicebackends.aigateway.envoyproxy.io",
        "backendsecuritypolicies.aigateway.envoyproxy.io",
        "backends.gateway.envoyproxy.io",
        "envoyproxies.gateway.envoyproxy.io",
        "envoyextensionpolicies.gateway.envoyproxy.io",
        "gatewayclasses.gateway.networking.k8s.io",
        "backendtlspolicies.gateway.networking.k8s.io",
    ],
)
def test_crd_is_installed(crd: str, k8s_apiextensions_v1) -> None:
    k8s_apiextensions_v1.read_custom_resource_definition(crd)


def _condition(obj: dict, kind: str) -> dict:
    for condition in obj.get("status", {}).get("conditions", []):
        if condition["type"] == kind:
            return condition
    raise AssertionError(f"no {kind} condition in {obj['metadata']['name']} status")


@pytest.mark.live
def test_gatewayclass_is_accepted(k8s_custom_objects) -> None:
    gatewayclass = k8s_custom_objects.get_cluster_custom_object(
        "gateway.networking.k8s.io", "v1", "gatewayclasses", GATEWAYCLASS_NAME
    )
    assert _condition(gatewayclass, "Accepted")["status"] == "True"


@pytest.mark.live
def test_gateway_is_programmed(k8s_custom_objects) -> None:
    gateway = k8s_custom_objects.get_namespaced_custom_object(
        "gateway.networking.k8s.io", "v1", "burritbot-net", "gateways", GATEWAY_NAME
    )
    assert _condition(gateway, "Programmed")["status"] == "True"


@pytest.mark.live
def test_ai_gateway_controller_is_available(k8s_apps_v1) -> None:
    namespace = _app(AIGW_CONTROLLER_APP)["spec"]["destination"]["namespace"]
    deployment = k8s_apps_v1.read_namespaced_deployment(_controller()["fullnameOverride"], namespace)
    assert deployment.status.available_replicas, f"{namespace}/{deployment.metadata.name} has no available replica"
