# ABOUTME: Phase C4 test — deploy/ai-gateway/kustomization.yaml references the C2 + C3 manifests.
# ABOUTME: Asserts no remaining Phase-C TODO comments after the greenfield resources land.

from __future__ import annotations

import re

import pytest

from conftest import PROJECT_ROOT
from helpers.manifest_graph import kustomization_files


KUSTOMIZATION = PROJECT_ROOT / "deploy" / "ai-gateway" / "kustomization.yaml"

# Repo-relative files deploy/ai-gateway must render, through the per-directory
# kustomizations it references (#76).
EXPECTED_REFS = [
    "ai-gateway/envoy/gatewayclass.yaml",
    "ai-gateway/envoy/gateway.yaml",
    "ai-gateway/envoy/vertex-ai-backend.yaml",
    "ai-gateway/nemo-guardrails/deployment.yaml",
    "ai-gateway/nemo-guardrails/configmap-config.yaml",
    "ai-gateway/nemo-guardrails/configmap-rails.yaml",
    "ai-gateway/llm-guard/deployment.yaml",
    "ai-gateway/llm-guard/configmap.yaml",
]


@pytest.mark.static
@pytest.mark.parametrize("ref", EXPECTED_REFS, ids=lambda r: r.split("/", 1)[-1])
def test_kustomization_references(ref: str) -> None:
    rendered = kustomization_files(PROJECT_ROOT, KUSTOMIZATION.parent)
    assert ref in rendered, (
        f"deploy/ai-gateway/kustomization.yaml does not render {ref}"
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
