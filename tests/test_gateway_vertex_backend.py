# ABOUTME: Resolves every route backendRef in ai-gateway/envoy/gateway.yaml to a defined backend,
# ABOUTME: and checks the Vertex AI AIServiceBackend chain authenticates via WIF, never a key file.

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

from conftest import PROJECT_ROOT, TERRAFORM_DIR


GATEWAY = PROJECT_ROOT / "ai-gateway" / "envoy" / "gateway.yaml"

# Directories holding the resources that gateway.yaml routes to.
MANIFEST_DIRS = [
    PROJECT_ROOT / "ai-gateway",
    PROJECT_ROOT / "apps",
]

# The backend each route kind's rule backendRefs resolve to.
ROUTE_BACKEND_KIND = {
    "HTTPRoute": "Service",
    "AIGatewayRoute": "AIServiceBackend",
}

VERTEX_BACKEND = "vertex-ai-gemini"
WIF_ANNOTATION_KEY = "iam.gke.io/gcp-service-account"


def _all_docs(path: Path) -> list[dict]:
    with path.open() as fp:
        return [d for d in yaml.safe_load_all(fp) if d]


def _tree_docs() -> list[dict]:
    docs: list[dict] = []
    for root in MANIFEST_DIRS:
        for path in sorted(root.rglob("*.yaml")):
            docs.extend(_all_docs(path))
    return docs


def _find(kind: str, namespace: str, name: str) -> dict | None:
    for doc in _tree_docs():
        meta = doc.get("metadata", {})
        if (
            doc.get("kind") == kind
            and meta.get("namespace") == namespace
            and meta.get("name") == name
        ):
            return doc
    return None


def _route_backend_refs() -> list[tuple[str, str, str]]:
    """Collect (route kind, namespace, name) for every rule backendRef in gateway.yaml."""
    refs: list[tuple[str, str, str]] = []
    for doc in _all_docs(GATEWAY):
        kind = doc["kind"]
        if kind not in ROUTE_BACKEND_KIND:
            continue
        route_ns = doc["metadata"]["namespace"]
        for rule in doc.get("spec", {}).get("rules", []) or []:
            for ref in rule.get("backendRefs", []) or []:
                refs.append((kind, ref.get("namespace", route_ns), ref["name"]))
    return refs


def _gateway() -> dict:
    gateways = [d for d in _all_docs(GATEWAY) if d["kind"] == "Gateway"]
    assert len(gateways) == 1, f"expected one Gateway in gateway.yaml, got {len(gateways)}"
    return gateways[0]


def _vertex_backend() -> dict:
    ns = _gateway()["metadata"]["namespace"]
    backend = _find("AIServiceBackend", ns, VERTEX_BACKEND)
    assert backend is not None, f"no AIServiceBackend {ns}/{VERTEX_BACKEND} in the tree"
    return backend


def _envoy_backend() -> dict:
    ai_backend = _vertex_backend()
    ref = ai_backend["spec"]["backendRef"]
    assert ref.get("kind") == "Backend", f"AIServiceBackend backendRef kind is {ref.get('kind')!r}"
    assert ref.get("group") == "gateway.envoyproxy.io", (
        f"AIServiceBackend backendRef group is {ref.get('group')!r}"
    )
    ns = ref.get("namespace", ai_backend["metadata"]["namespace"])
    backend = _find("Backend", ns, ref["name"])
    assert backend is not None, f"no Envoy Gateway Backend {ns}/{ref['name']} in the tree"
    return backend


def _targets(policy: dict, group: str, kind: str, name: str) -> bool:
    return any(
        t.get("group") == group and t.get("kind") == kind and t.get("name") == name
        for t in policy.get("spec", {}).get("targetRefs", []) or []
    )


def _tf_variable_default(name: str) -> str:
    text = (TERRAFORM_DIR / "variables.tf").read_text()
    match = re.search(
        rf'variable\s+"{name}"\s*\{{[^}}]*?default\s*=\s*"([^"]+)"', text, re.S
    )
    assert match, f"variables.tf has no string default for {name}"
    return match.group(1)


@pytest.mark.static
def test_route_backend_refs_are_collected() -> None:
    """Guard against the resolution check below passing vacuously."""
    names = {name for kind, _, name in _route_backend_refs() if kind == "AIGatewayRoute"}
    assert VERTEX_BACKEND in names, (
        f"gateway.yaml AIGatewayRoute backendRefs {sorted(names)} do not include "
        f"{VERTEX_BACKEND}"
    )


@pytest.mark.static
@pytest.mark.parametrize(
    "route_kind,namespace,name",
    _route_backend_refs(),
    ids=[f"{kind}:{ns}/{name}" for kind, ns, name in _route_backend_refs()],
)
def test_route_backend_ref_resolves(route_kind: str, namespace: str, name: str) -> None:
    target_kind = ROUTE_BACKEND_KIND[route_kind]
    assert _find(target_kind, namespace, name) is not None, (
        f"gateway.yaml {route_kind} backendRef {namespace}/{name} has no matching "
        f"{target_kind} in the repo"
    )


@pytest.mark.static
def test_vertex_backend_speaks_vertex_ai() -> None:
    schema = _vertex_backend()["spec"].get("schema", {})
    assert schema.get("name") == "GCPVertexAI", (
        f"AIServiceBackend {VERTEX_BACKEND} schema is {schema.get('name')!r}, "
        f"expected GCPVertexAI"
    )


@pytest.mark.static
def test_vertex_backend_endpoint_is_vertex_ai() -> None:
    endpoints = _envoy_backend()["spec"].get("endpoints", [])
    assert len(endpoints) == 1, f"expected one Vertex AI endpoint, got {endpoints}"
    fqdn = endpoints[0].get("fqdn", {})
    assert fqdn.get("hostname", "").endswith("-aiplatform.googleapis.com"), (
        f"Backend hostname {fqdn.get('hostname')!r} is not a Vertex AI regional endpoint"
    )
    assert fqdn.get("port") == 443, f"Backend port is {fqdn.get('port')!r}, expected 443"


@pytest.mark.static
def test_vertex_backend_has_tls_policy() -> None:
    backend = _envoy_backend()
    name = backend["metadata"]["name"]
    hostname = backend["spec"]["endpoints"][0]["fqdn"]["hostname"]
    policies = [
        d
        for d in _tree_docs()
        if d.get("kind") == "BackendTLSPolicy"
        and d["metadata"].get("namespace") == backend["metadata"]["namespace"]
        and _targets(d, "gateway.envoyproxy.io", "Backend", name)
    ]
    assert len(policies) == 1, f"expected one BackendTLSPolicy targeting Backend {name}"
    validation = policies[0]["spec"]["validation"]
    assert validation.get("hostname") == hostname, (
        f"BackendTLSPolicy validates {validation.get('hostname')!r}, Backend is {hostname!r}"
    )
    assert validation.get("wellKnownCACertificates") == "System"


@pytest.mark.static
def test_vertex_backend_authenticates_via_wif() -> None:
    """GCPCredentials with neither key file nor external WIF config uses ADC.

    On GKE, ADC resolves through Workload Identity to the GSA bound to the
    Envoy proxy pod's KSA. ADC is only accepted by the v1beta1 API; v1alpha1
    demands a key file or an external-OIDC WIF config.
    """
    ai_backend = _vertex_backend()
    policies = [
        d
        for d in _tree_docs()
        if d.get("kind") == "BackendSecurityPolicy"
        and d["metadata"].get("namespace") == ai_backend["metadata"]["namespace"]
        and _targets(d, "aigateway.envoyproxy.io", "AIServiceBackend", VERTEX_BACKEND)
    ]
    assert len(policies) == 1, (
        f"expected one BackendSecurityPolicy targeting AIServiceBackend {VERTEX_BACKEND}"
    )
    policy = policies[0]
    assert policy["apiVersion"] == "aigateway.envoyproxy.io/v1beta1", (
        f"BackendSecurityPolicy is {policy['apiVersion']}; ADC needs v1beta1"
    )
    assert policy["spec"].get("type") == "GCPCredentials"
    creds = policy["spec"].get("gcpCredentials", {})
    assert "credentialsFile" not in creds, "Vertex AI auth must not use a JSON key file"
    assert "workloadIdentityFederationConfig" not in creds, (
        "external-OIDC WIF is not needed on GKE; use the pod's Workload Identity"
    )
    hostname = _envoy_backend()["spec"]["endpoints"][0]["fqdn"]["hostname"]
    assert hostname == f"{creds.get('region')}-aiplatform.googleapis.com", (
        f"BackendSecurityPolicy region {creds.get('region')!r} does not match "
        f"Backend hostname {hostname!r}"
    )
    assert creds.get("projectName"), "BackendSecurityPolicy has no projectName"


@pytest.mark.static
def test_gateway_proxy_service_account_is_wif_bound() -> None:
    """The Envoy proxy pod (where ADC runs) has a fixed KSA annotated with the gateway GSA."""
    gateway = _gateway()
    infra = gateway["spec"].get("infrastructure", {})
    params = infra.get("parametersRef", {})
    assert params.get("group") == "gateway.envoyproxy.io"
    assert params.get("kind") == "EnvoyProxy"
    envoy_proxy = _find("EnvoyProxy", gateway["metadata"]["namespace"], params.get("name"))
    assert envoy_proxy is not None, f"Gateway parametersRef EnvoyProxy {params} not in the tree"
    ksa = (
        envoy_proxy["spec"]["provider"]["kubernetes"]
        .get("envoyServiceAccount", {})
        .get("name")
    )
    assert ksa, "EnvoyProxy does not pin envoyServiceAccount.name"

    gsa_email = infra.get("annotations", {}).get(WIF_ANNOTATION_KEY, "")
    expected_id = _tf_variable_default("ai_gateway_service_account_id")
    assert gsa_email.startswith(f"{expected_id}@"), (
        f"Gateway {WIF_ANNOTATION_KEY} annotation {gsa_email!r} does not name the "
        f"{expected_id} GSA"
    )

    iam = (TERRAFORM_DIR / "iam.tf").read_text()
    assert re.search(r'resource\s+"google_service_account"\s+"ai_gateway"', iam)
    assert re.search(
        r'role\s*=\s*"roles/aiplatform\.user"\s*\n\s*member\s*=\s*'
        r'"serviceAccount:\$\{google_service_account\.ai_gateway\.email\}"',
        iam,
    ), "ai_gateway GSA lacks roles/aiplatform.user"
    assert re.search(
        r"service_account_id\s*=\s*google_service_account\.ai_gateway\.name\s*\n"
        r'\s*role\s*=\s*"roles/iam\.workloadIdentityUser"\s*\n'
        rf'\s*member\s*=\s*"serviceAccount:\$\{{var\.project_id\}}\.svc\.id\.goog\[[^/\]]+/{ksa}\]"',
        iam,
    ), f"no workloadIdentityUser binding from KSA {ksa} to the ai_gateway GSA"
