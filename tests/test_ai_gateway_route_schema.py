# ABOUTME: Holds the AIGatewayRoute and its ExtProc wiring to the fields the upstream CRDs define,
# ABOUTME: so ServerSideApply neither rejects nor silently strips them (issue #49).

from __future__ import annotations

import copy

import pytest
import yaml

from conftest import PROJECT_ROOT


GATEWAY = PROJECT_ROOT / "ai-gateway" / "envoy" / "gateway.yaml"

NAMESPACE = "burritbot-net"
GATEWAY_NAME = "burritbot-ai-gateway"
ROUTE_NAME = "burritbot-gemini-route"
EXTPROC_POLICY_NAME = "burritbot-guardrails"

# Envoy AI Gateway aigateway.envoyproxy.io/v1beta1 AIGatewayRoute (api/v1beta1/
# ai_gateway_route.go). There is no targetRefs, schema or filters field: the
# route attaches to a Gateway by parentRefs, the client schema is fixed to
# OpenAI, and the controller inserts its own ext_proc into the HTTPRoute it
# generates. Anything else is an unknown field.
ROUTE_SPEC_FIELDS = {"parentRefs", "hostnames", "rules", "llmRequestCosts"}
ROUTE_RULE_FIELDS = {
    "name",
    "backendRefs",
    "matches",
    "timeouts",
    "streamIdleTimeout",
    "modelsOwnedBy",
    "modelsCreatedAt",
    "excludeFromModelsEndpoint",
}
ROUTE_MATCH_FIELDS = {"headers"}
ROUTE_BACKEND_REF_FIELDS = {
    "name",
    "namespace",
    "group",
    "kind",
    "modelNameOverride",
    "headerMutation",
    "bodyMutation",
    "weight",
    "priority",
}

# The header the AI Gateway sets from the request body's model before routing.
MODEL_HEADER = "x-ai-eg-model"

# Envoy Gateway gateway.envoyproxy.io/v1alpha1 EnvoyExtensionPolicy ExtProc
# (api/v1alpha1/ext_proc_types.go). backendRef (singular) is refused by CEL.
EXTPROC_FIELDS = {
    "backendRefs",
    "backendSettings",
    "messageTimeout",
    "failOpen",
    "processingMode",
    "shadowMode",
    "metadata",
    "statusOnError",
}
BODY_MODES = {"Streamed", "Buffered", "BufferedPartial", "FullDuplexStreamed"}
EXTPROC_TARGET_KINDS = {"Gateway", "ListenerSet", "HTTPRoute", "GRPCRoute", "UDPRoute", "TCPRoute", "TLSRoute"}

# The guardrails scanners, in filter-chain order.
EXPECTED_EXTPROC_BACKENDS = [("nemo-guardrails", 8000), ("llm-guard", 8000)]


def _docs() -> list[dict]:
    with GATEWAY.open(encoding="utf-8") as fp:
        return [d for d in yaml.safe_load_all(fp) if d]


def _one(docs: list[dict], api_version: str, kind: str, name: str) -> dict:
    found = [
        d for d in docs
        if d["apiVersion"] == api_version
        and d["kind"] == kind
        and d["metadata"]["name"] == name
        and d["metadata"].get("namespace") == NAMESPACE
    ]
    assert len(found) == 1, f"expected one {api_version} {kind} {NAMESPACE}/{name} in gateway.yaml, got {len(found)}"
    return found[0]


def _route(docs: list[dict]) -> dict:
    return _one(docs, "aigateway.envoyproxy.io/v1beta1", "AIGatewayRoute", ROUTE_NAME)


def _extproc_policy(docs: list[dict]) -> dict:
    return _one(docs, "gateway.envoyproxy.io/v1alpha1", "EnvoyExtensionPolicy", EXTPROC_POLICY_NAME)


def route_schema_violations(route: dict) -> list[str]:
    """Fields the upstream AIGatewayRoute CRD does not define, and parentRefs it refuses."""
    out: list[str] = []
    spec = route["spec"]
    out += [f"spec.{k}" for k in sorted(spec.keys() - ROUTE_SPEC_FIELDS)]
    for i, parent in enumerate(spec.get("parentRefs") or []):
        if parent.get("kind", "Gateway") != "Gateway":
            out.append(f"spec.parentRefs[{i}].kind {parent['kind']!r} (only Gateway is supported)")
    for i, rule in enumerate(spec.get("rules") or []):
        out += [f"spec.rules[{i}].{k}" for k in sorted(rule.keys() - ROUTE_RULE_FIELDS)]
        for j, match in enumerate(rule.get("matches") or []):
            out += [f"spec.rules[{i}].matches[{j}].{k}" for k in sorted(match.keys() - ROUTE_MATCH_FIELDS)]
        for j, ref in enumerate(rule.get("backendRefs") or []):
            out += [f"spec.rules[{i}].backendRefs[{j}].{k}" for k in sorted(ref.keys() - ROUTE_BACKEND_REF_FIELDS)]
    return out


def extproc_violations(policy: dict) -> list[str]:
    """ExtProc entries the upstream EnvoyExtensionPolicy CRD would refuse."""
    out: list[str] = []
    for i, ext in enumerate(policy["spec"].get("extProc") or []):
        out += [f"spec.extProc[{i}].{k}" for k in sorted(ext.keys() - EXTPROC_FIELDS)]
        for direction in ("request", "response"):
            mode = ((ext.get("processingMode") or {}).get(direction) or {}).get("body")
            if mode is not None and mode not in BODY_MODES:
                out.append(f"spec.extProc[{i}].processingMode.{direction}.body {mode!r}")
    for i, target in enumerate(policy["spec"].get("targetRefs") or []):
        if target.get("group") != "gateway.networking.k8s.io" or target.get("kind") not in EXTPROC_TARGET_KINDS:
            out.append(f"spec.targetRefs[{i}] {target.get('group')}/{target.get('kind')}")
    return out


# --- the route against the AIGatewayRoute CRD -----------------------------


@pytest.mark.static
def test_route_uses_only_crd_fields() -> None:
    violations = route_schema_violations(_route(_docs()))
    assert not violations, f"AIGatewayRoute {ROUTE_NAME} sets fields the CRD does not define: {violations}"


@pytest.mark.static
def test_route_attaches_to_the_gateway() -> None:
    parents = _route(_docs())["spec"].get("parentRefs") or []
    assert [(p.get("kind", "Gateway"), p["name"]) for p in parents] == [("Gateway", GATEWAY_NAME)], (
        f"AIGatewayRoute {ROUTE_NAME} parentRefs {parents} do not name Gateway {GATEWAY_NAME}"
    )


@pytest.mark.static
def test_route_matches_on_the_model_header_the_gateway_sets() -> None:
    names = {
        h["name"]
        for rule in _route(_docs())["spec"]["rules"]
        for match in rule.get("matches") or []
        for h in match.get("headers") or []
    }
    assert names == {MODEL_HEADER}, f"AIGatewayRoute {ROUTE_NAME} matches headers {sorted(names)}, not {MODEL_HEADER}"


# --- the guardrails ExtProc against the EnvoyExtensionPolicy CRD ----------


@pytest.mark.static
def test_extproc_policy_uses_only_crd_fields() -> None:
    violations = extproc_violations(_extproc_policy(_docs()))
    assert not violations, f"EnvoyExtensionPolicy {EXTPROC_POLICY_NAME} would be refused: {violations}"


@pytest.mark.static
def test_extproc_policy_covers_the_gateway() -> None:
    """Every route on the choke point, the audience route and the generated AI route alike."""
    targets = _extproc_policy(_docs())["spec"].get("targetRefs") or []
    assert [(t["group"], t["kind"], t["name"]) for t in targets] == [
        ("gateway.networking.k8s.io", "Gateway", GATEWAY_NAME)
    ], f"EnvoyExtensionPolicy {EXTPROC_POLICY_NAME} targets {targets}"


@pytest.mark.static
def test_extproc_chains_both_scanners_with_buffered_bodies() -> None:
    entries = _extproc_policy(_docs())["spec"].get("extProc") or []
    backends = [
        (ref["name"], ref.get("port"))
        for ext in entries
        for ref in ext.get("backendRefs") or []
    ]
    assert backends == EXPECTED_EXTPROC_BACKENDS, f"ExtProc backends {backends} != {EXPECTED_EXTPROC_BACKENDS}"
    for ext in entries:
        mode = ext.get("processingMode") or {}
        assert mode.get("request", {}).get("body") == "Buffered", f"{ext['backendRefs']} request body not Buffered"
        assert mode.get("response", {}).get("body") == "Buffered", f"{ext['backendRefs']} response body not Buffered"


# --- mutation tests: the pre-#49 shapes are caught ------------------------


@pytest.mark.static
@pytest.mark.parametrize(
    "field,value",
    [
        ("targetRefs", [{"group": "gateway.networking.k8s.io", "kind": "HTTPRoute", "name": "burritbot-audience"}]),
        ("schema", {"name": "OpenAI"}),
        ("filters", [{"type": "ExtProc", "extProc": {"backendRef": {"name": "llm-guard", "port": 8000}}}]),
    ],
)
def test_mutation_pre_49_route_field_is_caught(field: str, value: object) -> None:
    route = copy.deepcopy(_route(_docs()))
    route["spec"][field] = value
    assert f"spec.{field}" in route_schema_violations(route)


@pytest.mark.static
def test_mutation_httproute_parent_is_caught() -> None:
    route = copy.deepcopy(_route(_docs()))
    route["spec"]["parentRefs"][0]["kind"] = "HTTPRoute"
    assert any("parentRefs[0].kind" in v for v in route_schema_violations(route))


@pytest.mark.static
def test_mutation_singular_backend_ref_is_caught() -> None:
    policy = copy.deepcopy(_extproc_policy(_docs()))
    ext = policy["spec"]["extProc"][0]
    ext["backendRef"] = ext.pop("backendRefs")[0]
    assert "spec.extProc[0].backendRef" in extproc_violations(policy)


@pytest.mark.static
def test_mutation_pre_49_body_mode_spelling_is_caught() -> None:
    policy = copy.deepcopy(_extproc_policy(_docs()))
    policy["spec"]["extProc"][1]["processingMode"]["request"]["body"] = "BUFFERED"
    assert "spec.extProc[1].processingMode.request.body 'BUFFERED'" in extproc_violations(policy)
