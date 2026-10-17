# ABOUTME: Each timeout on the guarded path outlasts every hop inside it (#92, #109, #119): a GKE load balancer's backend
# ABOUTME: timeout, the frontend's guarded timeout, the burritbot-audience route, BurritBot's gateway and Vertex route.

from __future__ import annotations

import copy
import importlib.util
import re
import sys
from pathlib import Path
from types import ModuleType

import pytest
import yaml

from conftest import PROJECT_ROOT
from helpers.manifest_graph import (
    GATEWAY_API,
    ROUTE_KINDS,
    Manifest,
    collect_refs,
    load_manifests,
    synced_manifests,
    synced_patches,
)


GATEWAY_FILE = PROJECT_ROOT / "ai-gateway" / "envoy" / "gateway.yaml"
FRONTEND_MAIN = PROJECT_ROOT / "apps" / "audience-frontend" / "backend" / "main.py"
BURRITBOT_APP = PROJECT_ROOT / "apps" / "burritbot" / "app.py"

AUDIENCE_ROUTE = "burritbot-audience"
AI_ROUTE = "burritbot-gemini-route"
EXTPROC_POLICY = "burritbot-guardrails"

# The guarded path, outermost first. Phone -> frontend (guarded timeout) ->
# gateway: the guardrails ext_proc on the request -> burritbot-audience route
# (route timeout) -> guarded BurritBot (gateway timeout) -> gateway again: the
# guardrails ext_proc on the request -> AIGatewayRoute (route timeout) ->
# Vertex -> the guardrails ext_proc on the response -> BurritBot -> the
# guardrails ext_proc on the response -> frontend.
#
# Envoy starts a route timeout once the request has passed every decoder
# filter, and stops it when the upstream response is complete, before the
# encoder filters run. So a route timeout covers neither direction of the
# guardrails ext_proc on its own pass, and the caller of each pass must.
# Each ext_proc message is held to its messageTimeout, whatever the
# adapter does inside it.
#
# Without timeouts.request, Envoy Gateway leaves Envoy's 15s route default
# on an HTTPRoute, and Envoy AI Gateway sets 60s on an AIGatewayRoute rule
# (api/v1beta1/ai_gateway_route.go, v1.2.0).
#
# In front of the frontend, phones come in through a GKE Gateway (#57):
# GatewayClass gke-l7-global-external-managed, a global external
# Application Load Balancer. Its backend service timeout defaults to 30s,
# and only a GCPBackendPolicy on the Service (spec.default.timeoutSec)
# changes it. It has to outlast GUARDED_TIMEOUT_SECONDS, or a long guarded
# prompt gets the load balancer's 502/504 instead of the frontend's own
# error. Source: https://docs.cloud.google.com/kubernetes-engine/docs/how-to/configure-gateway-resources
# (backend service timeout), read 2026-10-17.

GKE_GATEWAY_CLASS_PREFIX = "gke-l7-"
GKE_NETWORKING = "networking.gke.io"
GKE_BACKEND_TIMEOUT_DEFAULT = 30.0
FRONTEND_SERVICE = ("audience", "audience-frontend")


def _docs(path: Path) -> list[dict]:
    return [d for d in yaml.safe_load_all(path.read_text(encoding="utf-8")) if d]


def _find(docs: list[dict], kind: str, name: str) -> dict:
    for doc in docs:
        if doc["kind"] == kind and doc["metadata"]["name"] == name:
            return doc
    raise AssertionError(f"{kind} {name} not found in {GATEWAY_FILE}")


def _seconds(duration: str) -> float:
    match = re.fullmatch(r"(\d+(?:\.\d+)?)(ms|s|m)", duration)
    assert match, f"unparseable duration {duration!r}"
    value, unit = float(match.group(1)), match.group(2)
    return value * {"ms": 0.001, "s": 1, "m": 60}[unit]


def _load(path: Path, name: str) -> ModuleType:
    """Import a fresh copy of a module, so it reads the environment as it is now."""
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader, f"cannot load {path}"
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _route_request_timeouts(route: dict) -> list[float | None]:
    """Each rule's timeouts.request in seconds, or None where the rule sets none."""
    out: list[float | None] = []
    for rule in route["spec"]["rules"]:
        request = (rule.get("timeouts") or {}).get("request")
        out.append(_seconds(request) if request else None)
    return out


def budget_violations(docs: list[dict], gateway_timeout: float, frontend_timeout: float) -> list[str]:
    """Every timeout on the guarded path that would fire before the hops inside it finish."""
    out: list[str] = []
    policy = _find(docs, "EnvoyExtensionPolicy", EXTPROC_POLICY)
    # One pass through the gateway: every ext_proc entry on the request, then on the response.
    scans = 2 * sum(_seconds(ext["messageTimeout"]) for ext in policy["spec"]["extProc"])

    vertex = _route_request_timeouts(_find(docs, "AIGatewayRoute", AI_ROUTE))
    if None in vertex:
        out.append(f"AIGatewayRoute {AI_ROUTE} leaves a rule on the 60s AI Gateway default; set timeouts.request")
    model_call = scans + max((t for t in vertex if t is not None), default=60.0)
    if gateway_timeout <= model_call:
        out.append(
            f"BurritBot GATEWAY_TIMEOUT_SECONDS {gateway_timeout:g} is not above its gateway pass "
            f"({scans:g}s of ext_proc plus the {AI_ROUTE} route timeout = {model_call:g}s)"
        )

    audience = _route_request_timeouts(_find(docs, "HTTPRoute", AUDIENCE_ROUTE))
    if None in audience:
        out.append(f"HTTPRoute {AUDIENCE_ROUTE} leaves a rule on Envoy's 15s route default; set timeouts.request")
    for seconds in (t if t is not None else 15.0 for t in audience):
        if seconds <= gateway_timeout:
            out.append(
                f"HTTPRoute {AUDIENCE_ROUTE} route timeout {seconds:g}s is not above BurritBot's "
                f"GATEWAY_TIMEOUT_SECONDS {gateway_timeout:g}"
            )
    audience_pass = scans + max(t if t is not None else 15.0 for t in audience)
    if frontend_timeout <= audience_pass:
        out.append(
            f"frontend GUARDED_TIMEOUT_SECONDS {frontend_timeout:g} is not above its gateway pass "
            f"({scans:g}s of ext_proc plus the {AUDIENCE_ROUTE} route timeout = {audience_pass:g}s)"
        )
    return out


def load_balancer_violations(manifests: list[Manifest], frontend_timeout: float) -> list[str]:
    """Every GKE Gateway route to the frontend whose load balancer would give up before the frontend does."""
    out: list[str] = []
    refs = collect_refs(manifests)
    gke_gateways = {
        (m.namespace, m.name)
        for m in manifests
        if m.group == GATEWAY_API
        and m.kind == "Gateway"
        and m.doc["spec"].get("gatewayClassName", "").startswith(GKE_GATEWAY_CLASS_PREFIX)
    }
    routes = {
        ref.source.label: ref.source
        for ref in refs
        if ref.field == "parentRef"
        and (ref.group, ref.kind) == (GATEWAY_API, "Gateway")
        and (ref.namespace, ref.name) in gke_gateways
    }
    fronted = False
    for _, route in sorted(routes.items()):
        for rule in route.doc["spec"].get("rules", []):
            backends = {
                (b.get("namespace", route.namespace), b["name"])
                for b in rule.get("backendRefs", [])
                if b.get("group", "") == "" and b.get("kind", "Service") == "Service"
            }
            if FRONTEND_SERVICE not in backends:
                continue
            fronted = True
            request = (rule.get("timeouts") or {}).get("request")
            if request and _seconds(request) <= frontend_timeout:
                out.append(
                    f"{route.label} route timeout {request} is not above the frontend's "
                    f"GUARDED_TIMEOUT_SECONDS {frontend_timeout:g}"
                )
    if not fronted:
        return out

    namespace, name = FRONTEND_SERVICE
    policies = [
        ref.source
        for ref in refs
        if ref.field == "targetRef"
        and ref.source.group == GKE_NETWORKING
        and ref.source.kind == "GCPBackendPolicy"
        and (ref.group, ref.kind, ref.namespace, ref.name) == ("", "Service", namespace, name)
    ]
    if not policies:
        out.append(
            f"Service {namespace}/{name} sits behind a GKE Gateway with no GCPBackendPolicy, so the load "
            f"balancer keeps its {GKE_BACKEND_TIMEOUT_DEFAULT:g}s backend timeout; set timeoutSec above "
            f"GUARDED_TIMEOUT_SECONDS {frontend_timeout:g}"
        )
    for policy in policies:
        timeout = (policy.doc["spec"].get("default") or {}).get("timeoutSec")
        seconds = float(timeout) if timeout is not None else GKE_BACKEND_TIMEOUT_DEFAULT
        if seconds <= frontend_timeout:
            out.append(
                f"{policy.label} timeoutSec {seconds:g} is not above the frontend's "
                f"GUARDED_TIMEOUT_SECONDS {frontend_timeout:g}"
            )
    return out


def frontend_exposure_violations(manifests: list[Manifest], patches: list[tuple[str, dict | None, object]]) -> list[str]:
    """Every way to the frontend from outside the cluster that load_balancer_violations cannot see.

    That rule reads only GKE Gateway routes and the GCPBackendPolicy on the
    Service. A LoadBalancer or NodePort Service, an Ingress (whose backend
    timeout a BackendConfig sets, also 30s by default) or a route through
    another Gateway would put phones in front of the frontend with a
    timeout nothing here holds above GUARDED_TIMEOUT_SECONDS.
    """
    out: list[str] = []
    namespace, name = FRONTEND_SERVICE
    for m in manifests:
        if (m.group, m.kind, m.namespace, m.name) == ("", "Service", namespace, name):
            kind = m.doc["spec"].get("type", "ClusterIP")
            if kind != "ClusterIP":
                out.append(f"{m.label} is type {kind}; phones reach it only through the GKE Gateway")
    for path, target, patch in patches:
        if isinstance(patch, dict):
            if (patch.get("kind"), (patch.get("metadata") or {}).get("name")) == ("Service", name):
                kind = (patch.get("spec") or {}).get("type")
                if kind not in (None, "ClusterIP"):
                    out.append(f"{path} patches Service {namespace}/{name} to type {kind}")
        elif (target or {}).get("kind") == "Service" and (target or {}).get("name") in (None, name):
            out.append(f"{path} has a JSON 6902 patch on Service {namespace}/{name}, which this check does not read")
    for m in manifests:
        if (m.group, m.kind) != ("networking.k8s.io", "Ingress") or m.namespace != namespace:
            continue
        spec = m.doc["spec"]
        backends = [spec.get("defaultBackend") or {}] + [
            p.get("backend") or {} for r in spec.get("rules") or [] for p in (r.get("http") or {}).get("paths") or []
        ]
        if any((b.get("service") or {}).get("name") == name for b in backends):
            out.append(f"{m.label} routes to Service {namespace}/{name}; phones reach it only through the GKE Gateway")
    gateways = {(m.namespace, m.name): m for m in manifests if (m.group, m.kind) == (GATEWAY_API, "Gateway")}
    for ref in collect_refs(manifests):
        route = ref.source
        if ref.field != "backendRef" or (ref.group, ref.kind, ref.namespace, ref.name) != ("", "Service", namespace, name):
            continue
        if route.kind not in ROUTE_KINDS:
            continue
        for parent in route.doc["spec"].get("parentRefs") or []:
            gateway = gateways.get((parent.get("namespace", route.namespace), parent["name"]))
            gateway_class = gateway.doc["spec"].get("gatewayClassName", "") if gateway else ""
            if route.kind != "HTTPRoute" or not gateway_class.startswith(GKE_GATEWAY_CLASS_PREFIX):
                out.append(
                    f"{route.label} routes to Service {namespace}/{name} through Gateway {parent['name']} "
                    f"(class {gateway_class or 'not in the repo'}), which the GKE load-balancer rule does not read"
                )
    return out


def _gateway_timeout() -> float:
    return _load(BURRITBOT_APP, "burritbot_app_timeout_budget").GATEWAY_TIMEOUT_SECONDS


def _frontend(monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    """Import main.py with the delivery overlay's /chat limits, which it needs to start (question 157)."""
    monkeypatch.setenv("AUDIENCE_TOKEN_LIMIT", "10/minute")
    monkeypatch.setenv("AUDIENCE_ADDRESS_LIMIT", "300/minute")
    return _load(FRONTEND_MAIN, "audience_frontend_main_timeout_budget")


@pytest.mark.static
def test_guarded_timeouts_outlast_the_hops_inside_them(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BURRITBOT_GUARDED", raising=False)
    violations = budget_violations(_docs(GATEWAY_FILE), _gateway_timeout(), _frontend(monkeypatch).GUARDED_TIMEOUT_SECONDS)
    assert not violations, "\n".join(violations)


@pytest.mark.static
def test_frontend_uses_the_guarded_timeout_on_the_guarded_target(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BURRITBOT_TARGET", "burritbot-guarded")
    frontend = _frontend(monkeypatch)
    _, _, timeout = frontend._resolve_target()
    assert timeout == frontend.GUARDED_TIMEOUT_SECONDS


@pytest.mark.static
def test_frontend_keeps_the_unguarded_timeout_on_the_unguarded_target(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BURRITBOT_TARGET", "burritbot-unguarded")
    frontend = _frontend(monkeypatch)
    _, _, timeout = frontend._resolve_target()
    assert timeout == frontend.UNGUARDED_TIMEOUT_SECONDS


def _drop_timeouts(docs: list[dict], kind: str, name: str) -> None:
    for rule in _find(docs, kind, name)["spec"]["rules"]:
        rule.pop("timeouts", None)


def _raise_message_timeouts(docs: list[dict]) -> None:
    for ext in _find(docs, "EnvoyExtensionPolicy", EXTPROC_POLICY)["spec"]["extProc"]:
        ext["messageTimeout"] = "30s"


@pytest.mark.static
@pytest.mark.parametrize(
    ("mutate", "gateway_delta", "frontend_timeout", "expected"),
    [
        (lambda docs: None, 0.0, 10.0, "frontend GUARDED_TIMEOUT_SECONDS 10"),
        (lambda docs: _drop_timeouts(docs, "HTTPRoute", AUDIENCE_ROUTE), 0.0, None, "Envoy's 15s route default"),
        (lambda docs: _drop_timeouts(docs, "AIGatewayRoute", AI_ROUTE), 0.0, None, "60s AI Gateway default"),
        (lambda docs: None, -1000.0, None, "is not above its gateway pass"),
        (lambda docs: None, 1000.0, None, "is not above BurritBot's"),
        (_raise_message_timeouts, 0.0, None, "is not above its gateway pass"),
    ],
    ids=[
        "frontend-10s",
        "audience-route-default",
        "vertex-route-default",
        "gateway-timeout-short",
        "audience-route-short",
        "message-timeouts-raised",
    ],
)
def test_mutation_short_timeout_is_caught(
    monkeypatch: pytest.MonkeyPatch, mutate, gateway_delta: float, frontend_timeout: float | None, expected: str
) -> None:
    monkeypatch.delenv("BURRITBOT_GUARDED", raising=False)
    docs = copy.deepcopy(_docs(GATEWAY_FILE))
    mutate(docs)
    gateway_timeout = max(_gateway_timeout() + gateway_delta, 1.0)
    frontend = frontend_timeout if frontend_timeout is not None else _frontend(monkeypatch).GUARDED_TIMEOUT_SECONDS
    violations = budget_violations(docs, gateway_timeout, frontend)
    assert any(expected in v for v in violations), violations


def _gke_exposure(policy_timeout: int | None, route_timeout: str | None = None) -> list[Manifest]:
    """The #57 shape: a GKE Gateway, an HTTPRoute to the frontend and, unless None, its GCPBackendPolicy."""
    namespace, name = FRONTEND_SERVICE
    rule: dict = {"backendRefs": [{"name": name, "port": 80}]}
    if route_timeout:
        rule["timeouts"] = {"request": route_timeout}
    docs = [
        {
            "apiVersion": f"{GATEWAY_API}/v1",
            "kind": "Gateway",
            "metadata": {"name": "audience", "namespace": namespace},
            "spec": {
                "gatewayClassName": "gke-l7-global-external-managed",
                "listeners": [{"name": "https", "protocol": "HTTPS", "port": 443}],
            },
        },
        {
            "apiVersion": f"{GATEWAY_API}/v1",
            "kind": "HTTPRoute",
            "metadata": {"name": "audience", "namespace": namespace},
            "spec": {"parentRefs": [{"name": "audience"}], "rules": [rule]},
        },
    ]
    if policy_timeout is not None:
        docs.append(
            {
                "apiVersion": f"{GKE_NETWORKING}/v1",
                "kind": "GCPBackendPolicy",
                "metadata": {"name": name, "namespace": namespace},
                "spec": {
                    "default": {"timeoutSec": policy_timeout},
                    "targetRef": {"group": "", "kind": "Service", "name": name},
                },
            }
        )
    return [Manifest("synthetic.yaml", doc) for doc in docs]


@pytest.mark.static
def test_frontend_service_is_where_the_load_balancer_rule_looks() -> None:
    namespace, name = FRONTEND_SERVICE
    services = [m for m in load_manifests(PROJECT_ROOT) if (m.group, m.kind, m.namespace, m.name) == ("", "Service", namespace, name)]
    assert services, f"Service {namespace}/{name} not found; the GKE load-balancer rule would check nothing"


@pytest.mark.static
def test_gke_load_balancer_outlasts_the_frontend(monkeypatch: pytest.MonkeyPatch) -> None:
    violations = load_balancer_violations(load_manifests(PROJECT_ROOT), _frontend(monkeypatch).GUARDED_TIMEOUT_SECONDS)
    assert not violations, "\n".join(violations)


@pytest.mark.static
def test_gke_policy_above_the_frontend_timeout_passes(monkeypatch: pytest.MonkeyPatch) -> None:
    frontend = _frontend(monkeypatch).GUARDED_TIMEOUT_SECONDS
    assert load_balancer_violations(_gke_exposure(int(frontend) + 10), frontend) == []


@pytest.mark.static
@pytest.mark.parametrize(
    ("policy_timeout", "route_timeout", "expected"),
    [
        (None, None, "no GCPBackendPolicy"),
        (30, None, "timeoutSec 30 is not above"),
        (125, None, "timeoutSec 125 is not above"),
        (135, "60s", "route timeout 60s is not above"),
    ],
    ids=["no-policy", "load-balancer-default", "equal-to-frontend", "route-timeout-short"],
)
def test_mutation_short_load_balancer_timeout_is_caught(
    monkeypatch: pytest.MonkeyPatch, policy_timeout: int | None, route_timeout: str | None, expected: str
) -> None:
    frontend = _frontend(monkeypatch).GUARDED_TIMEOUT_SECONDS
    violations = load_balancer_violations(_gke_exposure(policy_timeout, route_timeout), frontend)
    assert any(expected in v for v in violations), violations


# --- what ArgoCD syncs, delivery overlays included (#119) ----------------------
#
# The audience Application syncs presentations/<event>/deploy/audience, not
# deploy/audience. The #57 Gateway's hostname and certificate are per
# delivery, so it and its GCPBackendPolicy may land in that overlay, which
# load_manifests does not read.


def _repo_manifests(root: Path) -> list[Manifest]:
    return synced_manifests(root)


def _delivery_tree(
    root: Path, resources: list[dict], patches: list | None = None, target: dict | None = None
) -> Path:
    """A repo shaped like this one: the audience Application syncs a delivery overlay of deploy/audience."""
    namespace, name = FRONTEND_SERVICE
    overlay = "presentations/event/deploy/audience"
    kustomization: dict = {"resources": ["../../../../deploy/audience", "delivery-exposure.yaml"]}
    files: dict[str, object] = {
        "gitops/apps/30-audience.yaml": [{
            "apiVersion": "argoproj.io/v1alpha1",
            "kind": "Application",
            "metadata": {"name": "audience", "namespace": "argocd"},
            "spec": {
                "source": {"repoURL": "https://example.invalid/repo.git", "path": overlay},
                "destination": {"server": "https://kubernetes.default.svc", "namespace": namespace},
            },
        }],
        "deploy/audience/kustomization.yaml": [{"resources": ["../../apps/audience-frontend/k8s"]}],
        "apps/audience-frontend/k8s/kustomization.yaml": [{"resources": ["service.yaml"]}],
        "apps/audience-frontend/k8s/service.yaml": [{
            "apiVersion": "v1",
            "kind": "Service",
            "metadata": {"name": name, "namespace": namespace},
            "spec": {"type": "ClusterIP", "ports": [{"name": "http", "port": 80}]},
        }],
        f"{overlay}/delivery-exposure.yaml": resources,
    }
    if patches:
        entry: dict = {"path": "delivery-patch.yaml"}
        if target:
            entry["target"] = target
        kustomization["patches"] = [entry]
        files[f"{overlay}/delivery-patch.yaml"] = patches
    files[f"{overlay}/kustomization.yaml"] = [kustomization]
    for rel, docs in files.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(yaml.safe_dump_all(docs), encoding="utf-8")
    return root


def _overlay_docs(policy_timeout: int | None) -> list[dict]:
    """The #57 shape as a delivery overlay would write it: no metadata.namespace, the Application's applies."""
    docs = [copy.deepcopy(m.doc) for m in _gke_exposure(policy_timeout)]
    for doc in docs:
        del doc["metadata"]["namespace"]
    return docs


@pytest.mark.static
def test_gke_load_balancer_outlasts_the_frontend_in_what_argocd_syncs(monkeypatch: pytest.MonkeyPatch) -> None:
    manifests = _repo_manifests(PROJECT_ROOT)
    assert {("", "Service", *FRONTEND_SERVICE)} <= {(m.group, m.kind, m.namespace, m.name) for m in manifests}
    violations = load_balancer_violations(manifests, _frontend(monkeypatch).GUARDED_TIMEOUT_SECONDS)
    assert not violations, "\n".join(violations)


@pytest.mark.static
def test_frontend_has_no_exposure_the_load_balancer_rule_cannot_see() -> None:
    violations = frontend_exposure_violations(_repo_manifests(PROJECT_ROOT), synced_patches(PROJECT_ROOT))
    assert not violations, "\n".join(violations)


@pytest.mark.static
@pytest.mark.parametrize(
    ("policy_timeout", "expected"),
    [(None, "no GCPBackendPolicy"), (30, "timeoutSec 30 is not above"), (125, "timeoutSec 125 is not above")],
    ids=["no-policy", "load-balancer-default", "equal-to-frontend"],
)
def test_mutation_gateway_in_the_delivery_overlay_is_caught(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, policy_timeout: int | None, expected: str
) -> None:
    frontend = _frontend(monkeypatch).GUARDED_TIMEOUT_SECONDS
    root = _delivery_tree(tmp_path, _overlay_docs(policy_timeout))
    violations = load_balancer_violations(_repo_manifests(root), frontend)
    assert any(expected in v for v in violations), violations


@pytest.mark.static
def test_gateway_in_the_delivery_overlay_above_the_frontend_timeout_passes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    frontend = _frontend(monkeypatch).GUARDED_TIMEOUT_SECONDS
    root = _delivery_tree(tmp_path, _overlay_docs(int(frontend) + 10))
    assert load_balancer_violations(_repo_manifests(root), frontend) == []
    assert frontend_exposure_violations(_repo_manifests(root), synced_patches(root)) == []


def _service(kind: str) -> dict:
    namespace, name = FRONTEND_SERVICE
    return {"apiVersion": "v1", "kind": "Service", "metadata": {"name": name, "namespace": namespace}, "spec": {"type": kind}}


def _ingress() -> dict:
    namespace, name = FRONTEND_SERVICE
    return {
        "apiVersion": "networking.k8s.io/v1",
        "kind": "Ingress",
        "metadata": {"name": "audience", "namespace": namespace},
        "spec": {"rules": [{"http": {"paths": [
            {"path": "/", "pathType": "Prefix", "backend": {"service": {"name": name, "port": {"number": 80}}}},
        ]}}]},
    }


def _envoy_route() -> list[dict]:
    """The frontend behind the in-cluster Envoy gateway, whose route default is 15s."""
    docs = _overlay_docs(None)
    docs[0]["spec"]["gatewayClassName"] = "envoy-ai-gateway"
    return docs


@pytest.mark.static
@pytest.mark.parametrize(
    ("resources", "patches", "target", "expected"),
    [
        ([_service("LoadBalancer")], None, None, "is type LoadBalancer"),
        ([_service("NodePort")], None, None, "is type NodePort"),
        ([_ingress()], None, None, "delivery-exposure.yaml) routes to Service audience/audience-frontend"),
        (_envoy_route(), None, None, "(class envoy-ai-gateway), which the GKE load-balancer rule does not read"),
        ([], [{"apiVersion": "v1", "kind": "Service", "metadata": {"name": FRONTEND_SERVICE[1]}, "spec": {"type": "LoadBalancer"}}],
         None, "patches Service audience/audience-frontend to type LoadBalancer"),
        ([], [[{"op": "replace", "path": "/spec/type", "value": "LoadBalancer"}]],
         {"kind": "Service", "name": FRONTEND_SERVICE[1]}, "JSON 6902 patch on Service audience/audience-frontend"),
    ],
    ids=["load-balancer-service", "node-port-service", "ingress", "envoy-gateway-route", "overlay-patch", "overlay-json-patch"],
)
def test_mutation_exposure_outside_the_gke_gateway_is_caught(
    tmp_path: Path, resources: list[dict], patches: list | None, target: dict | None, expected: str
) -> None:
    configmap = {"apiVersion": "v1", "kind": "ConfigMap", "metadata": {"name": "x"}}
    root = _delivery_tree(tmp_path, resources or [configmap], patches, target)
    violations = frontend_exposure_violations(_repo_manifests(root), synced_patches(root))
    assert any(expected in v for v in violations), violations
