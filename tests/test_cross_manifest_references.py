# ABOUTME: Cross-manifest reference contract — every backendRef/parentRef/targetRef resolves to a
# ABOUTME: defined object ArgoCD syncs, on a port it exposes and a container serves; mutation tests prove each bites.

from __future__ import annotations

import copy
import shutil
from collections.abc import Callable
from pathlib import Path

import pytest

from conftest import PROJECT_ROOT
from helpers.manifest_graph import (
    GATEWAY_API,
    Manifest,
    collect_refs,
    load_manifests,
    missing_reference_grants,
    port_mismatches,
    service_backend_mismatches,
    synced_paths,
    unattachable_routes,
    unresolved_refs,
    unsynced_reference_grants,
)


# Each file can read correctly on its own while the pair disagrees; these
# checks only look at the agreement between files. None needs a cluster.
CHECKS: dict[str, Callable[[list[Manifest]], dict[str, str]]] = {
    "unresolved_refs": unresolved_refs,
    "port_mismatches": port_mismatches,
    "service_backend_mismatches": service_backend_mismatches,
    "missing_reference_grants": missing_reference_grants,
    "unattachable_routes": unattachable_routes,
}

# The ExtProc guardrails backends — the guarded path depends on both.
EXPECTED_EXTPROC_BACKENDS = {"nemo-guardrails", "llm-guard"}

# Stable keys of the references the mutation tests below break on purpose.
VERTEX_BACKEND_KEY = (
    "AIGatewayRoute burritbot-net/burritbot-gemini-route backendRef -> "
    "aigateway.envoyproxy.io/AIServiceBackend burritbot-net/vertex-ai-gemini"
)
AUDIENCE_BACKEND_KEY = (
    "HTTPRoute burritbot-net/burritbot-audience backendRef -> "
    "Service burritbot-guarded/burritbot-guarded:8080"
)
AUDIENCE_PARENT_KEY = (
    "HTTPRoute burritbot-net/burritbot-audience parentRef -> "
    "gateway.networking.k8s.io/Gateway burritbot-net/burritbot-ai-gateway"
)
GEMINI_PARENT_KEY = (
    "AIGatewayRoute burritbot-net/burritbot-gemini-route parentRef -> "
    "gateway.networking.k8s.io/Gateway burritbot-net/burritbot-ai-gateway"
)
GUARDRAILS_TARGET_KEY = (
    "EnvoyExtensionPolicy burritbot-net/burritbot-guardrails targetRef -> "
    "gateway.networking.k8s.io/Gateway burritbot-net/burritbot-ai-gateway"
)

MANIFESTS = load_manifests(PROJECT_ROOT)


def _find(manifests: list[Manifest], kind: str, namespace: str | None, name: str) -> dict:
    for m in manifests:
        if m.kind == kind and m.namespace == namespace and m.name == name:
            return m.doc
    raise LookupError(f"{kind} {namespace}/{name} not in manifests")


def _remove(manifests: list[Manifest], kind: str, namespace: str | None, name: str) -> None:
    doc = _find(manifests, kind, namespace, name)
    manifests[:] = [m for m in manifests if m.doc is not doc]


def _mutated(mutate: Callable[[list[Manifest]], None]) -> list[Manifest]:
    manifests = copy.deepcopy(MANIFESTS)
    mutate(manifests)
    return manifests


def _gemini_route(manifests: list[Manifest]) -> dict:
    return _find(manifests, "AIGatewayRoute", "burritbot-net", "burritbot-gemini-route")


def _guardrails_policy(manifests: list[Manifest]) -> dict:
    return _find(manifests, "EnvoyExtensionPolicy", "burritbot-net", "burritbot-guardrails")


def _extproc(manifests: list[Manifest], backend: str) -> dict:
    for ext in _guardrails_policy(manifests)["spec"]["extProc"]:
        for ref in ext["backendRefs"]:
            if ref["name"] == backend:
                return ref
    raise LookupError(f"no ExtProc entry for {backend}")


# --- the contract over the real repo ------------------------------------


@pytest.mark.static
def test_references_are_collected() -> None:
    """Guard against every check below passing because it collected nothing."""
    refs = collect_refs(MANIFESTS)
    extproc = {
        r.name for r in refs
        if r.source.kind == "EnvoyExtensionPolicy" and r.field == "backendRef" and r.kind == "Service"
    }
    assert extproc == EXPECTED_EXTPROC_BACKENDS, (
        f"ExtProc backendRefs collected {sorted(extproc)} != {sorted(EXPECTED_EXTPROC_BACKENDS)}"
    )
    fields = {(r.source.kind, r.field) for r in refs}
    for expected in [
        ("HTTPRoute", "parentRef"),
        ("HTTPRoute", "backendRef"),
        ("AIGatewayRoute", "parentRef"),
        ("AIGatewayRoute", "backendRef"),
        ("EnvoyExtensionPolicy", "targetRef"),
        ("EnvoyExtensionPolicy", "backendRef"),
    ]:
        assert expected in fields, f"no {expected[0]} {expected[1]} collected from the manifests"
    keys = {r.key for r in refs}
    for key in (VERTEX_BACKEND_KEY, AUDIENCE_BACKEND_KEY, AUDIENCE_PARENT_KEY, GEMINI_PARENT_KEY, GUARDRAILS_TARGET_KEY):
        assert key in keys, f"reference {key!r} not collected; the mutation tests below would be vacuous"
    services = [m for m in MANIFESTS if m.kind == "Service"]
    assert len(services) >= 5, f"only {len(services)} Services loaded; manifest roots moved?"


@pytest.mark.static
@pytest.mark.parametrize("check", sorted(CHECKS))
def test_no_violations(check: str) -> None:
    found = CHECKS[check](MANIFESTS)
    assert not found, "cross-manifest references broken:\n  " + "\n  ".join(found.values())


# --- mutation tests: inject each defect, confirm the check reports it ----


@pytest.mark.static
@pytest.mark.parametrize("backend,port", [("nemo-guardrails", 9000), ("llm-guard", 9100)])
def test_mutation_extproc_port_drift_is_caught(backend: str, port: int) -> None:
    """#23 as shipped: ExtProc backends on 9000/9100, Services on 8000."""
    manifests = _mutated(lambda ms: _extproc(ms, backend).update(port=port))
    found = port_mismatches(manifests)
    assert any(f"Service burritbot-net/{backend}:{port}" in k for k in found), found


@pytest.mark.static
def test_mutation_route_backend_to_nothing_is_caught() -> None:
    def mutate(ms: list[Manifest]) -> None:
        route = _find(ms, "HTTPRoute", "burritbot-net", "burritbot-audience")
        route["spec"]["rules"][0]["backendRefs"][0]["name"] = "burritbot-guardedd"

    found = unresolved_refs(_mutated(mutate))
    assert any("Service burritbot-guarded/burritbot-guardedd" in k for k in found), found


@pytest.mark.static
def test_mutation_undefined_ai_service_backend_is_caught() -> None:
    """#24 as shipped: the AIGatewayRoute names an AIServiceBackend defined nowhere."""
    manifests = _mutated(lambda ms: _remove(ms, "AIServiceBackend", "burritbot-net", "vertex-ai-gemini"))
    assert VERTEX_BACKEND_KEY in unresolved_refs(manifests)


@pytest.mark.static
def test_mutation_extproc_policy_to_undefined_gateway_is_caught() -> None:
    manifests = _mutated(lambda ms: _guardrails_policy(ms)["spec"]["targetRefs"][0].update(name="burritbot-gateway"))
    found = unresolved_refs(manifests)
    assert any("Gateway burritbot-net/burritbot-gateway" in k for k in found), found


@pytest.mark.static
def test_mutation_ai_route_parent_to_undefined_gateway_is_caught() -> None:
    manifests = _mutated(lambda ms: _gemini_route(ms)["spec"]["parentRefs"][0].update(name="burritbot-gateway"))
    found = unresolved_refs(manifests)
    assert any("Gateway burritbot-net/burritbot-gateway" in k for k in found), found


@pytest.mark.static
def test_mutation_extproc_to_undefined_service_is_caught() -> None:
    manifests = _mutated(lambda ms: _extproc(ms, "llm-guard").update(name="llm-gaurd"))
    found = unresolved_refs(manifests)
    assert any("Service burritbot-net/llm-gaurd:50051" in k for k in found), found


@pytest.mark.static
def test_mutation_container_port_drift_is_caught() -> None:
    """Service port and backendRef agree, but the container listens elsewhere."""
    def mutate(ms: list[Manifest]) -> None:
        svc = _find(ms, "Service", "burritbot-net", "nemo-guardrails")
        svc["spec"]["ports"][0]["targetPort"] = 7331
        deploy = _find(ms, "Deployment", "burritbot-net", "nemo-guardrails")
        deploy["spec"]["template"]["spec"]["containers"][0]["ports"][0]["containerPort"] = 9000

    manifests = _mutated(mutate)
    assert port_mismatches(manifests) == {}, "the Service-side port still agrees"
    found = service_backend_mismatches(manifests)
    assert "Service burritbot-net/nemo-guardrails:7331" in found, found


@pytest.mark.static
def test_mutation_named_target_port_drift_is_caught() -> None:
    def mutate(ms: list[Manifest]) -> None:
        deploy = _find(ms, "Deployment", "burritbot-net", "llm-guard")
        deploy["spec"]["template"]["spec"]["containers"][0]["ports"][0]["name"] = "api"

    found = service_backend_mismatches(_mutated(mutate))
    assert "Service burritbot-net/llm-guard:8000" in found, found


@pytest.mark.static
def test_mutation_service_selecting_no_pods_is_caught() -> None:
    def mutate(ms: list[Manifest]) -> None:
        svc = _find(ms, "Service", "burritbot-guarded", "burritbot-guarded")
        svc["spec"]["selector"]["burritbot.io/guarded"] = "false"

    found = service_backend_mismatches(_mutated(mutate))
    assert "Service burritbot-guarded/burritbot-guarded" in found, found


def _grant(manifests: list[Manifest]) -> dict:
    return _find(manifests, "ReferenceGrant", "burritbot-guarded", "burritbot-net-to-guarded")


def _listener(manifests: list[Manifest]) -> dict:
    return _find(manifests, "Gateway", "burritbot-net", "burritbot-ai-gateway")["spec"]["listeners"][0]


@pytest.mark.static
def test_mutation_missing_reference_grant_is_caught() -> None:
    """Found by this check (#26): the HTTPRoute's cross-namespace backend had no grant."""
    manifests = _mutated(lambda ms: _remove(ms, "ReferenceGrant", "burritbot-guarded", "burritbot-net-to-guarded"))
    assert missing_reference_grants(manifests).keys() == {AUDIENCE_BACKEND_KEY}


@pytest.mark.static
def test_mutation_reference_grant_for_wrong_namespace_is_caught() -> None:
    manifests = _mutated(lambda ms: _grant(ms)["spec"]["from"][0].update(namespace="audience"))
    assert missing_reference_grants(manifests).keys() == {AUDIENCE_BACKEND_KEY}


@pytest.mark.static
def test_mutation_reference_grant_for_other_service_is_caught() -> None:
    manifests = _mutated(lambda ms: _grant(ms)["spec"]["to"][0].update(name="burritbot-unguarded"))
    assert missing_reference_grants(manifests).keys() == {AUDIENCE_BACKEND_KEY}


GRANT_PATH = "apps/burritbot/k8s/referencegrant-guarded.yaml"
BURRITBOT_KUSTOMIZATION = "deploy/burritbot/kustomization.yaml"
# The delivery overlay of deploy/burritbot that the burritbot Application syncs (#82).
BURRITBOT_OVERLAY = "presentations/kubecon-na-2026/deploy/burritbot"
# The kustomization that lists the grant file; deploy/burritbot references its directory (#76).
GRANT_KUSTOMIZATION = "apps/burritbot/k8s/kustomization.yaml"
# The copied tree holds only the burritbot Application's sources, so the
# mutation cases resolve that Application alone.
BURRITBOT_APP = [m for m in MANIFESTS if m.kind == "Application" and m.name == "burritbot"]


@pytest.mark.static
def test_reference_grants_are_synced_by_argocd() -> None:
    """The grant must be applied by an Application, Kustomize or Directory source, not merely exist in the repo."""
    synced = synced_paths(PROJECT_ROOT, MANIFESTS)
    assert GRANT_PATH in synced, f"{GRANT_PATH} not applied by any ArgoCD Application: {sorted(synced)}"
    assert unsynced_reference_grants(MANIFESTS, synced) == {}


def _burritbot_tree(root: Path, drop: str | None = None) -> None:
    """Copy the overlay, deploy/burritbot and its resources into root, optionally dropping one resource line."""
    for rel in [BURRITBOT_KUSTOMIZATION, *(
        str(p.relative_to(PROJECT_ROOT))
        for d in ("apps/burritbot/k8s", BURRITBOT_OVERLAY)
        for p in (PROJECT_ROOT / d).glob("*.yaml")
    )]:
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(PROJECT_ROOT / rel, root / rel)
    if drop is not None:
        kust = root / GRANT_KUSTOMIZATION
        lines = kust.read_text(encoding="utf-8").splitlines(keepends=True)
        kept = [ln for ln in lines if drop not in ln]
        assert len(kept) == len(lines) - 1, f"expected exactly one {drop!r} line in {GRANT_KUSTOMIZATION}"
        kust.write_text("".join(kept), encoding="utf-8")


@pytest.mark.static
def test_copied_kustomization_still_syncs_grant(tmp_path: Path) -> None:
    """Positive control for the mutation below: the copied tree renders the grant."""
    _burritbot_tree(tmp_path)
    assert GRANT_PATH in synced_paths(tmp_path, BURRITBOT_APP)


@pytest.mark.static
def test_mutation_grant_dropped_from_kustomization_is_caught(tmp_path: Path) -> None:
    """The grant file stays in the repo, so missing_reference_grants passes; ArgoCD never applies it."""
    _burritbot_tree(tmp_path, drop="referencegrant-guarded.yaml")
    assert missing_reference_grants(MANIFESTS) == {}
    found = unsynced_reference_grants(MANIFESTS, synced_paths(tmp_path, BURRITBOT_APP))
    assert found.keys() == {"ReferenceGrant burritbot-guarded/burritbot-net-to-guarded"}


@pytest.mark.static
def test_kustomization_resource_naming_nothing_raises(tmp_path: Path) -> None:
    _burritbot_tree(tmp_path)
    (tmp_path / GRANT_PATH).unlink()
    with pytest.raises(FileNotFoundError, match="referencegrant-guarded.yaml"):
        synced_paths(tmp_path, BURRITBOT_APP)


@pytest.mark.static
def test_mutation_listener_refusing_route_namespace_is_caught() -> None:
    """Found by this check (#26): the listener admitted only application namespaces."""
    def mutate(ms: list[Manifest]) -> None:
        _listener(ms)["allowedRoutes"]["namespaces"] = {
            "from": "Selector",
            "selector": {"matchLabels": {"burritbot.io/layer": "application"}},
        }

    assert unattachable_routes(_mutated(mutate)).keys() == {AUDIENCE_PARENT_KEY, GEMINI_PARENT_KEY}


@pytest.mark.static
def test_mutation_selector_admitting_route_namespace_passes() -> None:
    """Positive control for the Selector path: a selector matching burritbot-net admits the route."""
    def mutate(ms: list[Manifest]) -> None:
        _listener(ms)["allowedRoutes"]["namespaces"] = {
            "from": "Selector",
            "selector": {"matchLabels": {"burritbot.io/layer": "the-net"}},
        }

    assert unattachable_routes(_mutated(mutate)) == {}


# --- the listener's other half: application namespaces stay off it ------
#
# decisions.md (#26, #52): the gateway is the single choke point, so
# application namespaces reach it only as backends. unattachable_routes
# proves the routes that exist are admitted; these probes prove a route
# an application namespace might add is refused, so a fix that widens the
# listener (from: All, the old application selector) cannot pass.

APPLICATION_NAMESPACES = {"burritbot-unguarded", "burritbot-guarded", "audience"}


def _probe_route(namespace: str) -> Manifest:
    return Manifest("probe", {
        "apiVersion": f"{GATEWAY_API}/v1",
        "kind": "HTTPRoute",
        "metadata": {"name": "probe", "namespace": namespace},
        "spec": {"parentRefs": [{"name": "burritbot-ai-gateway", "namespace": "burritbot-net"}]},
    })


def _probe_key(namespace: str) -> str:
    return f"HTTPRoute {namespace}/probe parentRef -> {GATEWAY_API}/Gateway burritbot-net/burritbot-ai-gateway"


def _application_namespaces(manifests: list[Manifest]) -> set[str]:
    return {
        m.name for m in manifests
        if m.kind == "Namespace" and m.doc["metadata"].get("labels", {}).get("burritbot.io/layer") == "application"
    }


def _application_routes_admitted(manifests: list[Manifest]) -> set[str]:
    """Application namespaces from which a new route would attach to the gateway."""
    namespaces = _application_namespaces(manifests)
    refused = unattachable_routes(manifests + [_probe_route(ns) for ns in namespaces])
    return {ns for ns in namespaces if _probe_key(ns) not in refused}


@pytest.mark.static
def test_application_namespaces_cannot_attach_routes() -> None:
    assert _application_namespaces(MANIFESTS) == APPLICATION_NAMESPACES, "namespace labels moved; probes would be vacuous"
    assert _application_routes_admitted(MANIFESTS) == set()


@pytest.mark.static
@pytest.mark.parametrize("namespaces", [
    {"from": "All"},
    {"from": "Selector", "selector": {"matchLabels": {"burritbot.io/layer": "application"}}},
    {"from": "Selector", "selector": {"matchLabels": {"app.kubernetes.io/part-of": "burritbot"}}},
])
def test_mutation_listener_admitting_application_routes_is_caught(namespaces: dict) -> None:
    """Widening the listener lets every application namespace claim the choke point."""
    manifests = _mutated(lambda ms: _listener(ms)["allowedRoutes"].update(namespaces=namespaces))
    assert _application_routes_admitted(manifests) == APPLICATION_NAMESPACES


@pytest.mark.static
def test_mutation_route_kind_not_admitted_is_caught() -> None:
    """The AIGatewayRoute attaches as the HTTPRoute it generates, so it is refused too."""
    manifests = _mutated(lambda ms: _listener(ms)["allowedRoutes"].update(kinds=[{"kind": "GRPCRoute"}]))
    assert unattachable_routes(manifests).keys() == {AUDIENCE_PARENT_KEY, GEMINI_PARENT_KEY}
