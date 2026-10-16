# ABOUTME: Holds the AIGatewayRoute and its ExtProc wiring to the fields the upstream CRDs define,
# ABOUTME: statically from v0.6.0 on (#49, #53) and live against the CRDs installed on the cluster.

from __future__ import annotations

import copy
import json
import re

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
#
# No chart pins the release, so these are the fields every release from the
# floor up serves (#53). v1beta1 first ships in v0.6.0; v0.2.0-v0.5.0 serve
# only v1alpha1. Checked against the ai-gateway-crds-helm CRDs of v0.6.0,
# v0.7.0, v1.0.0, v1.1.0 and v1.2.0. Later additions (hostnames in v0.7.0,
# rule name and streamIdleTimeout in v1.1.0, excludeFromModelsEndpoint in
# v1.2.0) would be pruned by an older controller, so they are refused here.
ROUTE_SPEC_FIELDS = {"parentRefs", "rules", "llmRequestCosts"}
ROUTE_RULE_FIELDS = {
    "backendRefs",
    "matches",
    "timeouts",
    "modelsOwnedBy",
    "modelsCreatedAt",
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
# Checked against the gateway-crds-helm CRDs of v1.7.0 (the Envoy Gateway
# that AI Gateway v0.6.0 builds against) and v1.9.2 (AI Gateway v1.2.0).
# shadowMode, statusOnError and the ListenerSet target arrived after v1.7.0.
EXTPROC_FIELDS = {
    "backendRefs",
    "backendSettings",
    "messageTimeout",
    "failOpen",
    "processingMode",
    "metadata",
}
BODY_MODES = {"Streamed", "Buffered", "BufferedPartial", "FullDuplexStreamed"}
EXTPROC_TARGET_KINDS = {"Gateway", "HTTPRoute", "GRPCRoute", "UDPRoute", "TCPRoute", "TLSRoute"}

# The guardrails scanners, in filter-chain order.
EXPECTED_EXTPROC_BACKENDS = [("nemo-guardrails", 8000), ("llm-guard", 8000)]

# Docs that pin the Envoy AI Gateway release this manifest needs.
AI_GATEWAY_FLOOR = "0.6"
# "Envoy AI Gateway 0.6+" in prose, "| Envoy AI Gateway | The Net | 0.6+ |" in scorecards.
FLOOR_PATTERN = re.compile(r"Envoy AI Gateway[\s|]*(?:The Net[\s|]*)?(\d+\.\d+)\+")
FLOOR_DOCS = [
    PROJECT_ROOT / "spec" / "phases" / "phase-05-the-net-ai-gateway.md",
    PROJECT_ROOT / "presentations" / "kubecon-na-2026" / "spec" / "SCORECARD.md",
    PROJECT_ROOT / "presentations" / "kubecon-na-2026" / "docs" / "SCORECARD.md",
]


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


# --- mutation tests: fields newer than the floor are caught (#53) ---------


@pytest.mark.static
@pytest.mark.parametrize(
    "rule_field,value,expected",
    [
        (None, ["burritbot.burritbot.local"], "spec.hostnames"),  # v0.7.0
        ("name", "gemini", "spec.rules[0].name"),  # v1.1.0
        ("streamIdleTimeout", "30s", "spec.rules[0].streamIdleTimeout"),  # v1.1.0
        ("excludeFromModelsEndpoint", True, "spec.rules[0].excludeFromModelsEndpoint"),  # v1.2.0
    ],
)
def test_mutation_route_field_newer_than_the_floor_is_caught(rule_field: str | None, value: object, expected: str) -> None:
    route = copy.deepcopy(_route(_docs()))
    if rule_field is None:
        route["spec"]["hostnames"] = value
    else:
        route["spec"]["rules"][0][rule_field] = value
    assert expected in route_schema_violations(route)


@pytest.mark.static
@pytest.mark.parametrize("field,value", [("shadowMode", False), ("statusOnError", {"code": 503})])
def test_mutation_extproc_field_newer_than_envoy_gateway_1_7_is_caught(field: str, value: object) -> None:
    policy = copy.deepcopy(_extproc_policy(_docs()))
    policy["spec"]["extProc"][0][field] = value
    assert f"spec.extProc[0].{field}" in extproc_violations(policy)


@pytest.mark.static
def test_mutation_listenerset_target_is_caught() -> None:
    policy = copy.deepcopy(_extproc_policy(_docs()))
    policy["spec"]["targetRefs"][0]["kind"] = "ListenerSet"
    assert any("targetRefs[0]" in v for v in extproc_violations(policy))


# --- the docs state the floor the manifest needs (#53) --------------------


@pytest.mark.static
@pytest.mark.parametrize("doc", FLOOR_DOCS, ids=lambda p: str(p.relative_to(PROJECT_ROOT)))
def test_doc_states_the_ai_gateway_floor(doc) -> None:
    """A 0.2+ floor promises releases that serve no v1beta1 AIGatewayRoute at all."""
    floors = FLOOR_PATTERN.findall(doc.read_text(encoding="utf-8"))
    assert floors, f"{doc} names no Envoy AI Gateway version"
    assert set(floors) == {AI_GATEWAY_FLOOR}, f"{doc} states Envoy AI Gateway {floors}+, the manifests need {AI_GATEWAY_FLOOR}+"


# --- live: the CRDs actually installed accept gateway.yaml (#53) ----------


def openapi_violations(obj: object, schema: dict, path: str = "") -> list[str]:
    """Unknown fields, missing required fields and out-of-enum values under a CRD's openAPIV3Schema.

    CEL rules (x-kubernetes-validations) are not evaluated; the static checks
    above hold the ones gateway.yaml depends on.
    """
    out: list[str] = []
    if isinstance(obj, dict):
        props = schema.get("properties")
        if props is not None and not schema.get("x-kubernetes-preserve-unknown-fields"):
            out += [f"{path}.{k}" for k in sorted(obj.keys() - props.keys())]
        out += [f"{path}.{k} (required)" for k in schema.get("required", []) if k not in obj]
        for k, v in obj.items():
            if props and k in props:
                out += openapi_violations(v, props[k], f"{path}.{k}")
    elif isinstance(obj, list):
        if "items" in schema:
            for i, v in enumerate(obj):
                out += openapi_violations(v, schema["items"], f"{path}[{i}]")
    elif "enum" in schema and obj not in schema["enum"]:
        out.append(f"{path} {obj!r} not in {schema['enum']}")
    return out


def _installed_schema(apiext, crd_name: str, version: str) -> dict:
    """The served openAPIV3Schema of an installed CRD, read through the live cluster client."""
    resp = apiext.read_custom_resource_definition(crd_name, _preload_content=False)
    crd = json.loads(resp.data)
    served = {v["name"]: v for v in crd["spec"]["versions"] if v.get("served")}
    assert version in served, f"installed CRD {crd_name} serves {sorted(served)}, not {version}"
    return served[version]["schema"]["openAPIV3Schema"]


LIVE_OBJECTS = [
    ("aigatewayroutes.aigateway.envoyproxy.io", "v1beta1", _route),
    ("envoyextensionpolicies.gateway.envoyproxy.io", "v1alpha1", _extproc_policy),
]


@pytest.mark.live
@pytest.mark.parametrize("crd_name,version,pick", LIVE_OBJECTS, ids=[c for c, _, _ in LIVE_OBJECTS])
def test_installed_crd_accepts_gateway_yaml(k8s_apiextensions_v1, crd_name: str, version: str, pick) -> None:
    schema = _installed_schema(k8s_apiextensions_v1, crd_name, version)
    obj = pick(_docs())
    violations = openapi_violations(obj, schema)
    assert not violations, f"installed {crd_name} {version} would refuse or strip {obj['metadata']['name']}: {violations}"


@pytest.mark.live
def test_installed_route_crd_refuses_the_pre_49_shape(k8s_apiextensions_v1) -> None:
    """The walker is not vacuous: the old targetRefs/schema/filters are unknown to the installed CRD."""
    schema = _installed_schema(k8s_apiextensions_v1, "aigatewayroutes.aigateway.envoyproxy.io", "v1beta1")
    route = copy.deepcopy(_route(_docs()))
    route["spec"]["targetRefs"] = [{"group": "gateway.networking.k8s.io", "kind": "HTTPRoute", "name": "burritbot-audience"}]
    route["spec"]["schema"] = {"name": "OpenAI"}
    route["spec"]["filters"] = [{"type": "ExtProc"}]
    assert {".spec.targetRefs", ".spec.schema", ".spec.filters"} <= set(openapi_violations(route, schema))
