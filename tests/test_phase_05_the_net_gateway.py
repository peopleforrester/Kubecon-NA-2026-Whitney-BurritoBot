# ABOUTME: Phase 5 "The Net — AI Gateway" tests — NeMo Guardrails, LLM Guard, Envoy.
# ABOUTME: Validates Colang rules, input/output scanners, and the Envoy AI Gateway route.

from __future__ import annotations

import pytest
import yaml

from conftest import PROJECT_ROOT


pytestmark = pytest.mark.phase5

GATEWAY_DIR = PROJECT_ROOT / "ai-gateway"
NEMO_DIR = GATEWAY_DIR / "nemo-guardrails"
LLM_GUARD_DIR = GATEWAY_DIR / "llm-guard"
ENVOY_DIR = GATEWAY_DIR / "envoy"

REQUIRED_NEMO_RAILS = {
    "burrito-only.co",
    "jailbreak-detect.co",
    "topic-enforcement.co",
    "output-sanitize.co",
}


@pytest.mark.static
def test_ai_gateway_tree_exists() -> None:
    assert GATEWAY_DIR.is_dir(), "ai-gateway/ is missing"
    assert NEMO_DIR.is_dir(), "ai-gateway/nemo-guardrails/ is missing"
    assert LLM_GUARD_DIR.is_dir(), "ai-gateway/llm-guard/ is missing"
    assert ENVOY_DIR.is_dir(), "ai-gateway/envoy/ is missing"


@pytest.mark.static
def test_nemo_colang_rails_present() -> None:
    """NeMo Guardrails ships the four named Colang rail files."""
    present = {p.name for p in NEMO_DIR.rglob("*.co")}
    missing = REQUIRED_NEMO_RAILS - present
    assert not missing, f"Missing NeMo Colang rails: {sorted(missing)}"


@pytest.mark.static
def test_nemo_config_yaml_valid() -> None:
    """NeMo Guardrails config.yaml is a valid YAML document."""
    path = NEMO_DIR / "config.yaml"
    assert path.exists(), "nemo-guardrails/config.yaml is missing"
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(doc, dict), "NeMo config.yaml is not a YAML mapping"
    assert "models" in doc or "rails" in doc, (
        "NeMo config must declare at least one of `models` or `rails`"
    )


@pytest.mark.static
def test_llm_guard_declares_input_and_output_scanners() -> None:
    """LLM Guard config declares both input and output scanners."""
    path = LLM_GUARD_DIR / "config.yaml"
    assert path.exists(), "llm-guard/config.yaml is missing"
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(doc, dict), "llm-guard config is not a YAML mapping"
    assert "input_scanners" in doc, "llm-guard config missing `input_scanners`"
    assert "output_scanners" in doc, "llm-guard config missing `output_scanners`"
    assert doc["input_scanners"], "llm-guard input_scanners list is empty"
    assert doc["output_scanners"], "llm-guard output_scanners list is empty"


@pytest.mark.static
def test_envoy_ai_gateway_manifest_exists() -> None:
    """Envoy AI Gateway route manifest exists and is valid YAML."""
    candidates = list(ENVOY_DIR.glob("*.yaml"))
    assert candidates, f"No YAML manifests found in {ENVOY_DIR}"
    found_gateway = False
    for path in candidates:
        for doc in yaml.safe_load_all(path.read_text(encoding="utf-8")):
            if not doc:
                continue
            kind = doc.get("kind", "")
            if kind in {"Gateway", "HTTPRoute", "AIGatewayRoute"}:
                found_gateway = True
    assert found_gateway, (
        "Envoy dir has no Gateway / HTTPRoute / AIGatewayRoute manifest"
    )


@pytest.mark.static
def test_guarded_path_namespace_is_burritbot_net() -> None:
    """Every AI gateway manifest targets the burritbot-net namespace, not `guardrails`."""
    offenders = []
    for path in GATEWAY_DIR.rglob("*.yaml"):
        text = path.read_text(encoding="utf-8")
        if "namespace: guardrails" in text:
            offenders.append(path.name)
    assert not offenders, (
        f"Found legacy `guardrails` namespace in: {offenders} — must be `burritbot-net`"
    )


# --- Live AI Gateway checks -------------------------------------------------


@pytest.mark.live
def test_nemo_guardrails_pod_running(k8s_core_v1) -> None:
    pods = k8s_core_v1.list_namespaced_pod(
        namespace="burritbot-net",
        label_selector="app.kubernetes.io/name=nemo-guardrails",
    )
    running = [p for p in pods.items if p.status and p.status.phase == "Running"]
    assert running, "No NeMo Guardrails pods Running in burritbot-net"


@pytest.mark.live
def test_envoy_ai_gateway_pod_running(k8s_core_v1) -> None:
    pods = k8s_core_v1.list_namespaced_pod(
        namespace="burritbot-net",
        label_selector="app.kubernetes.io/name=envoy-ai-gateway",
    )
    running = [p for p in pods.items if p.status and p.status.phase == "Running"]
    assert running, "No Envoy AI Gateway pods Running in burritbot-net"
