# ABOUTME: The controllers behind gatewayClassName envoy-ai-gateway: Envoy Gateway, the AI Gateway CRDs and
# ABOUTME: controller, and the GatewayClass, held to pinned versions, ControllerNamespace mode and the WIF binding.

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

from conftest import PROJECT_ROOT, TERRAFORM_DIR


APPS_DIR = PROJECT_ROOT / "gitops" / "apps"
GATEWAY_TREE = PROJECT_ROOT / "ai-gateway"
GATEWAY = GATEWAY_TREE / "envoy" / "gateway.yaml"
VERTEX_BACKEND_FILE = GATEWAY_TREE / "envoy" / "vertex-ai-backend.yaml"
DEPLOY_DIR = PROJECT_ROOT / "deploy" / "ai-gateway"
NAMESPACES_FILE = PROJECT_ROOT / "gitops" / "namespaces" / "namespaces.yaml"

CHART_REGISTRY = "docker.io/envoyproxy"
EG_CHART = "gateway-helm"
AIGW_CRDS_CHART = "ai-gateway-crds-helm"
AIGW_CHART = "ai-gateway-helm"
INSTALL_CHARTS = [EG_CHART, AIGW_CRDS_CHART, AIGW_CHART]

# Envoy Gateway's default controllerName; the AI Gateway values file sets it explicitly.
EG_CONTROLLER_NAME = "gateway.envoyproxy.io/gatewayclass-controller"

# ADC in a v1beta1 BackendSecurityPolicy (vertex-ai-backend.yaml) landed in v0.6.0.
AIGW_MIN_FOR_ADC = (0, 6, 0)

# The Envoy Gateway release each pinned AI Gateway release requires
# (egMinVersion in that release's site/docs/_vars.json). Bumping the
# AI Gateway pin without adding its row here fails the suite on purpose.
EG_MIN_FOR_AIGW = {
    (1, 2, 0): (1, 9, 2),
}

# The chart's controller.fullnameOverride default; it names the Service the
# Envoy Gateway extension manager dials and the MCP session Secret.
AIGW_CONTROLLER_NAME = "ai-gateway-controller"
AIGW_EXTENSION_PORT = 1063


def _docs(path: Path) -> list[dict]:
    return [d for d in yaml.safe_load_all(path.read_text(encoding="utf-8")) if d]


def _applications() -> list[dict]:
    return [
        doc
        for path in sorted(APPS_DIR.glob("*.yaml"))
        for doc in _docs(path)
        if doc.get("kind") == "Application"
    ]


def _chart_app(chart: str) -> dict:
    apps = [a for a in _applications() if a["spec"].get("source", {}).get("chart") == chart]
    assert len(apps) == 1, f"expected one Application installing {chart}, got {len(apps)}"
    return apps[0]


def _path_app(path: str) -> dict:
    apps = [a for a in _applications() if a["spec"].get("source", {}).get("path") == path]
    assert len(apps) == 1, f"expected one Application syncing {path}, got {len(apps)}"
    return apps[0]


def _values(app: dict) -> dict:
    return app["spec"]["source"].get("helm", {}).get("valuesObject", {}) or {}


def _semver(app: dict) -> tuple[int, int, int]:
    rev = str(app["spec"]["source"].get("targetRevision", ""))
    match = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)", rev)
    assert match, (
        f"{app['metadata']['name']} targetRevision {rev!r} is not an exact release pin"
    )
    return tuple(int(g) for g in match.groups())  # type: ignore[return-value]


def _wave(app: dict) -> int:
    return int(app["metadata"].get("annotations", {}).get("argocd.argoproj.io/sync-wave", "0"))


def _namespace(app: dict) -> str:
    return app["spec"]["destination"]["namespace"]


def _gateway() -> dict:
    gateways = [d for d in _docs(GATEWAY) if d["kind"] == "Gateway"]
    assert len(gateways) == 1, f"expected one Gateway in {GATEWAY.name}"
    return gateways[0]


def _eg_config() -> dict:
    return _values(_chart_app(EG_CHART)).get("config", {}).get("envoyGateway", {})


def _deployed_files() -> set[Path]:
    """Files the ai-gateway Application syncs, resolved from its kustomization."""
    kustomization = yaml.safe_load((DEPLOY_DIR / "kustomization.yaml").read_text())
    return {(DEPLOY_DIR / r).resolve() for r in kustomization.get("resources", [])}


def _gateway_classes() -> list[tuple[Path, dict]]:
    return [
        (path, doc)
        for path in sorted(GATEWAY_TREE.rglob("*.yaml"))
        for doc in _docs(path)
        if doc.get("kind") == "GatewayClass"
    ]


@pytest.mark.static
def test_gateway_class_is_defined_and_deployed() -> None:
    """The Gateway's gatewayClassName names a GatewayClass that the ai-gateway app syncs."""
    class_name = _gateway()["spec"]["gatewayClassName"]
    matches = [(p, d) for p, d in _gateway_classes() if d["metadata"]["name"] == class_name]
    assert len(matches) == 1, (
        f"expected one GatewayClass {class_name!r} under ai-gateway/, got {len(matches)}"
    )
    path, gateway_class = matches[0]
    assert path.resolve() in _deployed_files(), (
        f"{path.relative_to(PROJECT_ROOT)} is not a resource of "
        f"{(DEPLOY_DIR / 'kustomization.yaml').relative_to(PROJECT_ROOT)}"
    )
    controller = _eg_config().get("gateway", {}).get("controllerName", EG_CONTROLLER_NAME)
    assert gateway_class["spec"].get("controllerName") == controller, (
        f"GatewayClass {class_name} controllerName "
        f"{gateway_class['spec'].get('controllerName')!r} is not Envoy Gateway's {controller!r}"
    )


@pytest.mark.static
@pytest.mark.parametrize("chart", INSTALL_CHARTS)
def test_install_chart_is_pinned(chart: str) -> None:
    app = _chart_app(chart)
    assert app["spec"]["source"].get("repoURL") == CHART_REGISTRY, (
        f"{chart} repoURL is {app['spec']['source'].get('repoURL')!r}, expected {CHART_REGISTRY}"
    )
    _semver(app)
    assert "ServerSideApply=true" in app["spec"]["syncPolicy"].get("syncOptions", []), (
        f"{chart}: the Gateway API and AI Gateway CRDs exceed the client-side "
        f"last-applied annotation limit; sync with ServerSideApply"
    )


@pytest.mark.static
def test_ai_gateway_crds_and_controller_share_a_release() -> None:
    crds = _semver(_chart_app(AIGW_CRDS_CHART))
    controller = _semver(_chart_app(AIGW_CHART))
    assert crds == controller, f"AI Gateway CRDs {crds} and controller {controller} differ"
    assert controller >= AIGW_MIN_FOR_ADC, (
        f"AI Gateway {controller} predates {AIGW_MIN_FOR_ADC}, the first release whose "
        f"v1beta1 BackendSecurityPolicy accepts ADC"
    )


@pytest.mark.static
def test_envoy_gateway_meets_ai_gateway_minimum() -> None:
    aigw = _semver(_chart_app(AIGW_CHART))
    assert aigw in EG_MIN_FOR_AIGW, (
        f"no Envoy Gateway minimum recorded for AI Gateway {aigw}; add its egMinVersion"
    )
    eg = _semver(_chart_app(EG_CHART))
    assert eg >= EG_MIN_FOR_AIGW[aigw], (
        f"Envoy Gateway {eg} is below {EG_MIN_FOR_AIGW[aigw]}, the minimum for AI Gateway {aigw}"
    )


@pytest.mark.static
def test_envoy_gateway_extension_manager_dials_ai_gateway_controller() -> None:
    """The AI Gateway rewrites Envoy Gateway's xDS through the extension manager hooks."""
    config = _eg_config()
    assert config.get("extensionApis", {}).get("enableBackend") is True, (
        "Envoy Gateway must enable the Backend API (the Vertex AI Backend uses it)"
    )
    manager = config.get("extensionManager", {})
    fqdn = manager.get("service", {}).get("fqdn", {})
    controller_ns = _namespace(_chart_app(AIGW_CHART))
    expected = f"{AIGW_CONTROLLER_NAME}.{controller_ns}.svc.cluster.local"
    assert fqdn.get("hostname") == expected, (
        f"extension manager dials {fqdn.get('hostname')!r}, the controller Service is {expected}"
    )
    assert fqdn.get("port") == AIGW_EXTENSION_PORT
    hooks = manager.get("hooks", {}).get("xdsTranslator", {})
    assert {"Translation", "Cluster", "Route"} <= set(hooks.get("post", [])), (
        f"xdsTranslator post hooks {hooks.get('post')} miss Translation/Cluster/Route"
    )
    translation = hooks.get("translation", {})
    for kind in ("listener", "route", "cluster", "secret"):
        assert translation.get(kind, {}).get("includeAll") is True, (
            f"xdsTranslator.translation.{kind}.includeAll is not true"
        )
    assert _values(_chart_app(AIGW_CHART)).get("controller", {}).get(
        "fullnameOverride", AIGW_CONTROLLER_NAME
    ) == AIGW_CONTROLLER_NAME


@pytest.mark.static
def test_envoy_gateway_runs_proxies_in_controller_namespace() -> None:
    """ControllerNamespace mode, stated explicitly; the Terraform WIF binding targets it.

    GatewayNamespace mode would move the proxy pod and its KSA into
    burritbot-net, where require-burritbot-sidecar-naming (Enforce) rejects
    the ai-gateway-extproc and shutdown-manager containers.
    """
    deploy = _eg_config().get("provider", {}).get("kubernetes", {}).get("deploy", {})
    assert deploy.get("type") == "ControllerNamespace", (
        f"Envoy Gateway deploy.type is {deploy.get('type')!r}; set ControllerNamespace explicitly"
    )
    proxy_ns = _namespace(_chart_app(EG_CHART))

    gateway = _gateway()
    params = gateway["spec"]["infrastructure"]["parametersRef"]
    envoy_proxies = [
        d
        for d in _docs(VERTEX_BACKEND_FILE)
        if d["kind"] == "EnvoyProxy" and d["metadata"]["name"] == params["name"]
    ]
    assert len(envoy_proxies) == 1, f"no EnvoyProxy {params['name']}"
    ksa = envoy_proxies[0]["spec"]["provider"]["kubernetes"]["envoyServiceAccount"]["name"]

    iam = (TERRAFORM_DIR / "iam.tf").read_text()
    bound = re.findall(
        r"service_account_id\s*=\s*google_service_account\.ai_gateway\.name\s*\n"
        r'\s*role\s*=\s*"roles/iam\.workloadIdentityUser"\s*\n'
        r'\s*member\s*=\s*"serviceAccount:\$\{var\.project_id\}\.svc\.id\.goog\[([^\]]+)\]"',
        iam,
    )
    assert bound == [f"{proxy_ns}/{ksa}"], (
        f"ai_gateway WIF binding targets {bound}; the proxy KSA is {proxy_ns}/{ksa}"
    )


@pytest.mark.static
@pytest.mark.parametrize("chart", INSTALL_CHARTS)
def test_install_namespace_is_declared(chart: str) -> None:
    app = _chart_app(chart)
    assert "CreateNamespace=false" in app["spec"]["syncPolicy"].get("syncOptions", [])
    declared = {d["metadata"]["name"] for d in _docs(NAMESPACES_FILE) if d["kind"] == "Namespace"}
    assert _namespace(app) in declared, (
        f"{chart} installs into {_namespace(app)}, which namespaces.yaml does not declare"
    )


@pytest.mark.static
def test_sync_waves_install_controllers_before_the_gateway() -> None:
    """CRDs and Envoy Gateway, then the AI Gateway controller, then the Gateway itself.

    The controller's webhook adds the ExtProc sidecar to Envoy proxy pods at
    creation, so the Gateway must not get a proxy before the webhook exists.
    The webhook certificate comes from cert-manager, so the controller also
    follows cert-manager.
    """
    crds = _wave(_chart_app(AIGW_CRDS_CHART))
    eg = _wave(_chart_app(EG_CHART))
    controller = _wave(_chart_app(AIGW_CHART))
    gateway = _wave(_path_app("deploy/ai-gateway"))
    cert_manager = _wave(_chart_app("cert-manager"))
    assert max(crds, eg) < controller < gateway, (
        f"waves: crds {crds}, envoy-gateway {eg}, controller {controller}, gateway {gateway}"
    )
    assert cert_manager < controller, (
        f"controller wave {controller} does not follow cert-manager wave {cert_manager}"
    )


@pytest.mark.static
def test_ai_gateway_webhook_certificate_is_stable_under_argocd() -> None:
    """ArgoCD renders with helm template, so the chart's lookup-based self-signed cert regenerates."""
    webhook = _values(_chart_app(AIGW_CHART)).get("controller", {}).get("mutatingWebhook", {})
    assert webhook.get("certManager", {}).get("enable") is True, (
        "set controller.mutatingWebhook.certManager.enable so cert-manager owns the webhook cert"
    )


@pytest.mark.static
def test_mcp_session_seed_survives_rerender() -> None:
    """The chart's random MCP seed must not rotate on every ArgoCD render, nor sit in Git."""
    app = _chart_app(AIGW_CHART)
    session = (
        _values(app).get("controller", {}).get("mcp", {}).get("sessionEncryption", {})
    )
    assert not session.get("seed"), "the MCP session seed is a secret; keep it out of Git"
    if session.get("existingSecret"):
        return
    secret = f"{AIGW_CONTROLLER_NAME}-mcp-session-encryption"
    ignored = [
        d
        for d in app["spec"].get("ignoreDifferences", [])
        if d.get("kind") == "Secret"
        and d.get("name") == secret
        and d.get("namespace") == _namespace(app)
        and "/data" in d.get("jsonPointers", [])
    ]
    assert ignored, f"no ignoreDifferences on Secret {secret} /data"
    assert "RespectIgnoreDifferences=true" in app["spec"]["syncPolicy"].get("syncOptions", []), (
        "without RespectIgnoreDifferences a sync still overwrites the seed"
    )
