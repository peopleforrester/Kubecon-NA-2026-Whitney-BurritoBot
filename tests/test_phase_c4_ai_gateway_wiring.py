# ABOUTME: Phase C4 test — deploy/ai-gateway/kustomization.yaml references the C2 + C3 manifests.
# ABOUTME: Asserts no remaining Phase-C TODO comments, and that every gateway.yaml
# ABOUTME: backendRef port matches the port its Service actually exposes.

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

from conftest import PROJECT_ROOT


KUSTOMIZATION = PROJECT_ROOT / "deploy" / "ai-gateway" / "kustomization.yaml"

EXPECTED_REFS = [
    "../../ai-gateway/envoy/gateway.yaml",
    "../../ai-gateway/nemo-guardrails/deployment.yaml",
    "../../ai-gateway/nemo-guardrails/configmap-config.yaml",
    "../../ai-gateway/nemo-guardrails/configmap-rails.yaml",
    "../../ai-gateway/llm-guard/deployment.yaml",
    "../../ai-gateway/llm-guard/configmap.yaml",
]


def _kustomization() -> dict:
    with KUSTOMIZATION.open() as fp:
        for doc in yaml.safe_load_all(fp):
            if doc and doc.get("kind") == "Kustomization":
                return doc
    raise AssertionError("no Kustomization in deploy/ai-gateway/")


@pytest.mark.static
@pytest.mark.parametrize("ref", EXPECTED_REFS, ids=lambda r: r.rsplit("/", 1)[-1])
def test_kustomization_references(ref: str) -> None:
    k = _kustomization()
    resources = k.get("resources", []) or []
    assert ref in resources, (
        f"deploy/ai-gateway/kustomization.yaml missing reference to {ref}"
    )


@pytest.mark.static
def test_phase_c_todo_resolved() -> None:
    """Phase C TODOs must be gone now that C2 + C3 landed."""
    text = KUSTOMIZATION.read_text()
    leftover = re.findall(r"TODO\((?:critical-fixes-plan|phase-c)\)", text)
    assert not leftover, (
        f"deploy/ai-gateway/kustomization.yaml still has Phase C TODO "
        f"comments: {leftover}"
    )


# --- Gateway backendRef ↔ Service port cross-reference -------------------
#
# gateway.yaml was authored before the NeMo and LLM Guard Services existed,
# so its ExtProc filters named ports nothing listened on. Envoy could not
# reach either backend and the guarded path failed open. Same class of
# static cross-check as
# test_phase_c2_nemo_guardrails.py::test_deployment_mounts_match_configmap_names.

GATEWAY = PROJECT_ROOT / "ai-gateway" / "envoy" / "gateway.yaml"

# burritbot-guarded, nemo-guardrails, llm-guard. A rename that silently drops
# a backend out of the check trips this floor rather than passing vacuously.
MIN_CHECKED_REFS = 3


def _yaml_docs(path: Path) -> list[dict]:
    try:
        with path.open() as fp:
            return [d for d in yaml.safe_load_all(fp) if isinstance(d, dict)]
    except yaml.YAMLError:
        return []


def _service_ports() -> dict[tuple[str | None, str | None], set[int]]:
    """Map (namespace, name) to the set of ports each in-repo Service exposes."""
    index: dict[tuple[str | None, str | None], set[int]] = {}
    for path in sorted(PROJECT_ROOT.rglob("*.yaml")):
        if ".git" in path.parts:
            continue
        for doc in _yaml_docs(path):
            if doc.get("kind") != "Service":
                continue
            meta = doc.get("metadata", {}) or {}
            key = (meta.get("namespace"), meta.get("name"))
            ports = {
                port["port"]
                for port in (doc.get("spec", {}) or {}).get("ports", []) or []
                if isinstance(port, dict) and isinstance(port.get("port"), int)
            }
            index.setdefault(key, set()).update(ports)
    return index


def _ref_tuple(ref: dict, namespace: str | None) -> tuple[str | None, str | None, int | None]:
    """A backendRef without its own namespace inherits the enclosing document's."""
    return (ref.get("namespace") or namespace, ref.get("name"), ref.get("port"))


def _collect_backend_refs(
    node: object,
    namespace: str | None,
    out: list[tuple[str | None, str | None, int | None]],
) -> None:
    """Walk a manifest collecting every backendRef / backendRefs entry."""
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "backendRef" and isinstance(value, dict):
                out.append(_ref_tuple(value, namespace))
            elif key == "backendRefs" and isinstance(value, list):
                for ref in value:
                    if isinstance(ref, dict):
                        out.append(_ref_tuple(ref, namespace))
            else:
                _collect_backend_refs(value, namespace, out)
    elif isinstance(node, list):
        for item in node:
            _collect_backend_refs(item, namespace, out)


@pytest.mark.static
def test_gateway_backend_ports_match_services() -> None:
    """Every gateway.yaml backendRef port must be a port its Service exposes."""
    services = _service_ports()

    refs: list[tuple[str | None, str | None, int | None]] = []
    for doc in _yaml_docs(GATEWAY):
        _collect_backend_refs(doc, (doc.get("metadata", {}) or {}).get("namespace"), refs)

    checked = 0
    mismatches = []
    for namespace, name, port in refs:
        if port is None:
            # AIServiceBackend refs (vertex-ai-gemini) carry no port.
            continue
        exposed = services.get((namespace, name))
        if exposed is None:
            # Backend is not a Service defined in this repo; nothing to check.
            continue
        checked += 1
        if port not in exposed:
            mismatches.append(
                f"{namespace}/{name}: gateway.yaml targets port {port}, "
                f"Service exposes {sorted(exposed)}"
            )

    assert checked >= MIN_CHECKED_REFS, (
        f"only {checked} backendRef(s) resolved to an in-repo Service, expected at "
        f"least {MIN_CHECKED_REFS} — a backend was renamed and is no longer checked"
    )
    assert not mismatches, "gateway.yaml backendRef ports disagree with Services:\n" + "\n".join(
        mismatches
    )
