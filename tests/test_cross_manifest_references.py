# ABOUTME: Cross-manifest reference contract — every backendRef/parentRef/targetRef resolves to a
# ABOUTME: defined object, on a port it exposes and a container serves; mutation tests prove each check bites.

from __future__ import annotations

import copy
from typing import Callable

import pytest

from conftest import PROJECT_ROOT
from helpers.manifest_graph import (
    Manifest,
    collect_refs,
    load_manifests,
    missing_reference_grants,
    port_mismatches,
    service_backend_mismatches,
    unattachable_routes,
    unresolved_refs,
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


def _extproc(manifests: list[Manifest], backend: str) -> dict:
    for flt in _gemini_route(manifests)["spec"]["filters"]:
        ref = flt["extProc"]["backendRef"]
        if ref["name"] == backend:
            return ref
    raise LookupError(f"no ExtProc filter for {backend}")


# --- the contract over the real repo ------------------------------------


@pytest.mark.static
def test_references_are_collected() -> None:
    """Guard against every check below passing because it collected nothing."""
    refs = collect_refs(MANIFESTS)
    extproc = {
        r.name for r in refs
        if r.source.kind == "AIGatewayRoute" and r.field == "backendRef" and r.kind == "Service"
    }
    assert extproc == EXPECTED_EXTPROC_BACKENDS, (
        f"ExtProc backendRefs collected {sorted(extproc)} != {sorted(EXPECTED_EXTPROC_BACKENDS)}"
    )
    fields = {(r.source.kind, r.field) for r in refs}
    for expected in [
        ("HTTPRoute", "parentRef"),
        ("HTTPRoute", "backendRef"),
        ("AIGatewayRoute", "targetRef"),
        ("AIGatewayRoute", "backendRef"),
    ]:
        assert expected in fields, f"no {expected[0]} {expected[1]} collected from the manifests"
    keys = {r.key for r in refs}
    for key in (VERTEX_BACKEND_KEY, AUDIENCE_BACKEND_KEY, AUDIENCE_PARENT_KEY):
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
    """#23 as shipped: ExtProc filters on 9000/9100, Services on 8000."""
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
def test_mutation_extproc_to_undefined_service_is_caught() -> None:
    manifests = _mutated(lambda ms: _extproc(ms, "llm-guard").update(name="llm-gaurd"))
    found = unresolved_refs(manifests)
    assert any("Service burritbot-net/llm-gaurd:8000" in k for k in found), found


@pytest.mark.static
def test_mutation_container_port_drift_is_caught() -> None:
    """Service port and backendRef agree, but the container listens elsewhere."""
    def mutate(ms: list[Manifest]) -> None:
        svc = _find(ms, "Service", "burritbot-net", "nemo-guardrails")
        svc["spec"]["ports"][0]["targetPort"] = 8000
        deploy = _find(ms, "Deployment", "burritbot-net", "nemo-guardrails")
        deploy["spec"]["template"]["spec"]["containers"][0]["ports"][0]["containerPort"] = 9000

    manifests = _mutated(mutate)
    assert port_mismatches(manifests) == {}, "the Service-side port still agrees"
    found = service_backend_mismatches(manifests)
    assert "Service burritbot-net/nemo-guardrails:8000" in found, found


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


@pytest.mark.static
def test_mutation_listener_refusing_route_namespace_is_caught() -> None:
    """Found by this check (#26): the listener admitted only application namespaces."""
    def mutate(ms: list[Manifest]) -> None:
        _listener(ms)["allowedRoutes"]["namespaces"] = {
            "from": "Selector",
            "selector": {"matchLabels": {"burritbot.io/layer": "application"}},
        }

    assert unattachable_routes(_mutated(mutate)).keys() == {AUDIENCE_PARENT_KEY}


@pytest.mark.static
def test_mutation_selector_admitting_route_namespace_passes() -> None:
    """Positive control for the Selector path: a selector matching burritbot-net admits the route."""
    def mutate(ms: list[Manifest]) -> None:
        _listener(ms)["allowedRoutes"]["namespaces"] = {
            "from": "Selector",
            "selector": {"matchLabels": {"burritbot.io/layer": "the-net"}},
        }

    assert unattachable_routes(_mutated(mutate)) == {}


@pytest.mark.static
def test_mutation_route_kind_not_admitted_is_caught() -> None:
    manifests = _mutated(lambda ms: _listener(ms)["allowedRoutes"].update(kinds=[{"kind": "GRPCRoute"}]))
    assert unattachable_routes(manifests).keys() == {AUDIENCE_PARENT_KEY}
