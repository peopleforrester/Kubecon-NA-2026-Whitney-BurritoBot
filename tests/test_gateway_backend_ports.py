# ABOUTME: Cross-checks every port-bearing backendRef in ai-gateway/envoy/gateway.yaml against
# ABOUTME: the in-repo Service of that name, so ExtProc and route targets hit a listening port.

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from conftest import PROJECT_ROOT


GATEWAY = PROJECT_ROOT / "ai-gateway" / "envoy" / "gateway.yaml"

# Directories holding the Services that gateway.yaml routes to.
SERVICE_DIRS = [
    PROJECT_ROOT / "ai-gateway",
    PROJECT_ROOT / "apps",
]

# The guardrails ExtProc backends — Act 2 depends on both being reachable.
EXPECTED_EXTPROC_BACKENDS = {"nemo-guardrails", "llm-guard"}


def _all_docs(path: Path) -> list[dict]:
    with path.open() as fp:
        return [d for d in yaml.safe_load_all(fp) if d]


def _services() -> dict[tuple[str, str], dict]:
    """Map (namespace, name) -> Service doc for every Service in SERVICE_DIRS."""
    services: dict[tuple[str, str], dict] = {}
    for root in SERVICE_DIRS:
        for path in sorted(root.rglob("*.yaml")):
            for doc in _all_docs(path):
                if doc.get("kind") != "Service":
                    continue
                meta = doc["metadata"]
                services[(meta["namespace"], meta["name"])] = doc
    return services


def _backend_refs() -> list[tuple[str, str, str, int]]:
    """Collect (source, namespace, name, port) for every backendRef carrying a port.

    Covers HTTPRoute / AIGatewayRoute rule backendRefs and ExtProc filter
    backendRefs. backendRefs without a port (e.g. AIServiceBackend targets)
    are not Services and are skipped.
    """
    refs: list[tuple[str, str, str, int]] = []
    for doc in _all_docs(GATEWAY):
        kind = doc["kind"]
        route_ns = doc["metadata"]["namespace"]
        spec = doc.get("spec", {})
        candidates: list[tuple[str, dict]] = []
        for rule in spec.get("rules", []) or []:
            for ref in rule.get("backendRefs", []) or []:
                candidates.append((f"{kind} rule", ref))
        for flt in spec.get("filters", []) or []:
            ref = (flt.get("extProc") or {}).get("backendRef")
            if ref:
                candidates.append((f"{kind} ExtProc", ref))
        for source, ref in candidates:
            if "port" not in ref:
                continue
            refs.append(
                (source, ref.get("namespace", route_ns), ref["name"], ref["port"])
            )
    return refs


@pytest.mark.static
def test_extproc_backends_are_collected() -> None:
    """Guard against the cross-check below passing vacuously."""
    extproc = {name for source, _, name, _ in _backend_refs() if "ExtProc" in source}
    assert extproc == EXPECTED_EXTPROC_BACKENDS, (
        f"gateway.yaml ExtProc backendRefs {sorted(extproc)} != "
        f"{sorted(EXPECTED_EXTPROC_BACKENDS)}"
    )


@pytest.mark.static
@pytest.mark.parametrize(
    "source,namespace,name,port",
    _backend_refs(),
    ids=[f"{ns}/{name}:{port}" for _, ns, name, port in _backend_refs()],
)
def test_backend_ref_port_matches_service(
    source: str, namespace: str, name: str, port: int
) -> None:
    services = _services()
    svc = services.get((namespace, name))
    assert svc is not None, (
        f"gateway.yaml {source} backendRef {namespace}/{name} has no matching "
        f"Service in the repo"
    )
    exposed = [p["port"] for p in svc["spec"].get("ports", [])]
    assert port in exposed, (
        f"gateway.yaml {source} backendRef {namespace}/{name} targets port "
        f"{port}, but the Service exposes {exposed}"
    )
