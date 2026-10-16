# ABOUTME: Holds the documented Gateway API floor to the release that first serves every Gateway API object
# ABOUTME: the manifests apply (BackendTLSPolicy v1 needs v1.4, #74), and checks them live against the installed CRDs.

from __future__ import annotations

import copy
import re

import pytest

from conftest import PROJECT_ROOT
from helpers.crd_schema import installed_schema, openapi_violations
from helpers.manifest_graph import GATEWAY_API, Manifest, load_manifests


# The first Gateway API release whose standard-install.yaml serves each
# apiVersion/kind the manifests use, with the fields they set. Read from the
# release CRDs of v1.0.0, v1.1.0, v1.2.0, v1.2.1, v1.3.0, v1.4.0, v1.4.1,
# v1.5.1 and v1.6.1 (checked 2026-10-16); "1.0" means v1.0.0 or earlier.
#
# BackendTLSPolicy (vertex-ai-backend.yaml) is served only as v1alpha3, and
# only in the experimental channel, in v1.2 and v1.3; v1 arrives in v1.4.0.
# Gateway spec.infrastructure (gateway.yaml) is unknown to the v1.0 and v1.1
# standard CRDs. Envoy Gateway v1.7.0 and AI Gateway v0.6.0 build against
# gateway-api v1.4.1; Envoy Gateway v1.9.2 and AI Gateway v1.2.0 against v1.6.1.
FIRST_SERVED = {
    (f"{GATEWAY_API}/v1", "GatewayClass"): "1.0",
    (f"{GATEWAY_API}/v1", "Gateway"): "1.2",
    (f"{GATEWAY_API}/v1", "HTTPRoute"): "1.0",
    (f"{GATEWAY_API}/v1beta1", "ReferenceGrant"): "1.0",
    (f"{GATEWAY_API}/v1", "BackendTLSPolicy"): "1.4",
}

# Docs that pin the Gateway API release the manifests need.
GATEWAY_API_FLOOR = "1.4"
# "Gateway API v1.4+" in prose and scorecards, "Gateway API: **v1.4+**" in the skill.
FLOOR_PATTERN = re.compile(r"Gateway API[\s:*]*v(\d+\.\d+)")
FLOOR_DOCS = [
    PROJECT_ROOT / "spec" / "phases" / "phase-05-the-net-ai-gateway.md",
    PROJECT_ROOT / "presentations" / "kubecon-na-2026" / "spec" / "SCORECARD.md",
    PROJECT_ROOT / ".claude" / "skills" / "the-net-ai-gateway.md",
]

# CRD names for the live check.
CRD_PLURALS = {
    "GatewayClass": "gatewayclasses",
    "Gateway": "gateways",
    "HTTPRoute": "httproutes",
    "ReferenceGrant": "referencegrants",
    "BackendTLSPolicy": "backendtlspolicies",
}


def _gateway_api_objects(manifests: list[Manifest]) -> list[Manifest]:
    return [m for m in manifests if m.group == GATEWAY_API]


def _version_key(release: str) -> tuple[int, ...]:
    return tuple(int(p) for p in release.split("."))


def unrecorded_objects(manifests: list[Manifest]) -> list[str]:
    """Gateway API objects whose apiVersion/kind has no recorded first release."""
    return [
        f"{m.label} {m.doc['apiVersion']}"
        for m in _gateway_api_objects(manifests)
        if (m.doc["apiVersion"], m.kind) not in FIRST_SERVED
    ]


def required_floor(manifests: list[Manifest]) -> str:
    """The oldest Gateway API release that serves every Gateway API object in the manifests."""
    releases = [FIRST_SERVED[(m.doc["apiVersion"], m.kind)] for m in _gateway_api_objects(manifests)]
    return max(releases, key=_version_key)


def _manifests() -> list[Manifest]:
    return load_manifests(PROJECT_ROOT)


@pytest.mark.static
def test_every_gateway_api_object_has_a_recorded_first_release() -> None:
    unrecorded = unrecorded_objects(_manifests())
    assert not unrecorded, (
        "Gateway API objects with no recorded first release; read the release CRDs "
        f"(standard-install.yaml) and add them to FIRST_SERVED: {unrecorded}"
    )


@pytest.mark.static
def test_manifests_need_the_documented_gateway_api_floor() -> None:
    assert required_floor(_manifests()) == GATEWAY_API_FLOOR


@pytest.mark.static
@pytest.mark.parametrize("doc", FLOOR_DOCS, ids=lambda p: str(p.relative_to(PROJECT_ROOT)))
def test_doc_states_the_gateway_api_floor(doc) -> None:
    """A v1.2 floor promises releases that serve no BackendTLSPolicy v1 at all."""
    floors = FLOOR_PATTERN.findall(doc.read_text(encoding="utf-8"))
    assert floors, f"{doc} names no Gateway API version"
    assert set(floors) == {GATEWAY_API_FLOOR}, f"{doc} states Gateway API {floors}, the manifests need v{GATEWAY_API_FLOOR}+"


# --- mutation tests: the checks above are not vacuous ---------------------


def _backend_tls_policy(manifests: list[Manifest]) -> Manifest:
    (policy,) = [m for m in manifests if m.group == GATEWAY_API and m.kind == "BackendTLSPolicy"]
    return policy


@pytest.mark.static
def test_mutation_backend_tls_policy_sets_the_floor() -> None:
    """Without BackendTLSPolicy v1 the floor falls back to what Gateway needs."""
    manifests = _manifests()
    policy = _backend_tls_policy(manifests)
    assert policy.path == "ai-gateway/envoy/vertex-ai-backend.yaml"
    assert required_floor([m for m in manifests if m is not policy]) == "1.2"


@pytest.mark.static
def test_mutation_unrecorded_api_version_is_caught() -> None:
    """v1alpha3 is the experimental-channel BackendTLSPolicy of v1.2 and v1.3; it is not recorded."""
    manifests = _manifests()
    policy = _backend_tls_policy(manifests)
    doc = copy.deepcopy(policy.doc)
    doc["apiVersion"] = f"{GATEWAY_API}/v1alpha3"
    mutated = [Manifest(policy.path, doc) if m is policy else m for m in manifests]
    assert any("BackendTLSPolicy" in u and u.endswith("/v1alpha3") for u in unrecorded_objects(mutated))


@pytest.mark.static
@pytest.mark.parametrize(
    "text",
    ["- Envoy AI Gateway 0.6+, Gateway API v1.2", "| Envoy AI Gateway | The Net | 0.6+ | RED | Gateway API v1.2 |", "- Gateway API: **v1.2**"],
)
def test_mutation_old_doc_floor_is_caught(text: str) -> None:
    assert FLOOR_PATTERN.findall(text) == ["1.2"]


# --- live: the installed Gateway API CRDs accept every object ----------------


@pytest.mark.live
@pytest.mark.parametrize("manifest", _gateway_api_objects(load_manifests(PROJECT_ROOT)), ids=lambda m: m.label)
def test_installed_gateway_api_crd_accepts_manifest(k8s_apiextensions_v1, manifest: Manifest) -> None:
    version = manifest.doc["apiVersion"].split("/", 1)[1]
    schema = installed_schema(k8s_apiextensions_v1, f"{CRD_PLURALS[manifest.kind]}.{GATEWAY_API}", version)
    violations = openapi_violations(manifest.doc, schema)
    assert not violations, f"installed {manifest.kind} {version} CRD would refuse or strip {manifest.label}: {violations}"
