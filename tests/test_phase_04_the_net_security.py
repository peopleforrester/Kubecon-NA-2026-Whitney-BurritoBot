# ABOUTME: Phase 4 "The Net — Security" tests — Kyverno policies and Falco rules.
# ABOUTME: Validates burritbot.io labels, burritbot-* sidecar naming, and Falco tags.

from __future__ import annotations

import pytest
import yaml

from conftest import PROJECT_ROOT


pytestmark = pytest.mark.phase4

SECURITY_DIR = PROJECT_ROOT / "security"
KYVERNO_DIR = SECURITY_DIR / "kyverno" / "policies"
KYVERNO_TESTS_DIR = SECURITY_DIR / "kyverno" / "tests"
FALCO_DIR = SECURITY_DIR / "falco" / "rules"

REQUIRED_KYVERNO_POLICIES = {
    "require-burritbot-labels.yaml",
    "require-burritbot-sidecar-naming.yaml",
    "restrict-burritbot-network.yaml",
}

REQUIRED_BURRITBOT_LABELS = {
    "burritbot.io/layer",
    "burritbot.io/model-source",
    "burritbot.io/model-hash",
}

REQUIRED_FALCO_TAGS = {"burritbot", "the-net"}


@pytest.mark.static
def test_security_tree_exists() -> None:
    assert SECURITY_DIR.is_dir(), "security/ is missing"
    assert KYVERNO_DIR.is_dir(), "security/kyverno/policies/ is missing"
    assert FALCO_DIR.is_dir(), "security/falco/rules/ is missing"


@pytest.mark.static
def test_kyverno_required_policies_exist() -> None:
    """The three named Kyverno policies exist as YAML files."""
    present = {p.name for p in KYVERNO_DIR.glob("*.yaml")}
    missing = REQUIRED_KYVERNO_POLICIES - present
    assert not missing, f"Missing Kyverno policies: {sorted(missing)}"


@pytest.mark.static
def test_kyverno_policies_are_valid_yaml_and_kind() -> None:
    """Every Kyverno policy parses as YAML with kind: ClusterPolicy or Policy."""
    for path in KYVERNO_DIR.glob("*.yaml"):
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert doc is not None, f"{path.name} is empty"
        kind = doc.get("kind")
        assert kind in {"ClusterPolicy", "Policy"}, (
            f"{path.name} kind is {kind!r}, expected ClusterPolicy or Policy"
        )
        assert doc.get("apiVersion", "").startswith("kyverno.io/"), (
            f"{path.name} apiVersion is not kyverno.io/*"
        )


@pytest.mark.static
def test_require_labels_policy_enforces_burritbot_labels() -> None:
    """require-burritbot-labels.yaml enforces the full burritbot.io label set."""
    path = KYVERNO_DIR / "require-burritbot-labels.yaml"
    assert path.exists(), "require-burritbot-labels.yaml is missing"
    text = path.read_text(encoding="utf-8")
    missing = [lbl for lbl in REQUIRED_BURRITBOT_LABELS if lbl not in text]
    assert not missing, f"Kyverno require-labels policy missing labels: {missing}"


@pytest.mark.static
def test_sidecar_naming_policy_requires_burritbot_prefix() -> None:
    """require-burritbot-sidecar-naming.yaml enforces the burritbot-* sidecar prefix."""
    path = KYVERNO_DIR / "require-burritbot-sidecar-naming.yaml"
    assert path.exists(), "require-burritbot-sidecar-naming.yaml is missing"
    text = path.read_text(encoding="utf-8")
    assert "burritbot-" in text, (
        "sidecar naming policy does not reference the `burritbot-` prefix"
    )


@pytest.mark.static
def test_network_policy_locks_guarded_burritbot_to_burritbot_net() -> None:
    """restrict-burritbot-network.yaml references the burritbot-net namespace."""
    path = KYVERNO_DIR / "restrict-burritbot-network.yaml"
    assert path.exists(), "restrict-burritbot-network.yaml is missing"
    text = path.read_text(encoding="utf-8")
    assert "burritbot-net" in text, "network policy does not reference burritbot-net"


@pytest.mark.static
def test_falco_rules_tagged_burritbot_the_net() -> None:
    """At least one Falco rule file tags rules with [burritbot, the-net, ...]."""
    any_tagged = False
    for path in FALCO_DIR.glob("*.yaml"):
        text = path.read_text(encoding="utf-8")
        if "burritbot" in text and "the-net" in text:
            any_tagged = True
            break
    assert any_tagged, (
        f"No Falco rule file in {FALCO_DIR} tagged [burritbot, the-net, ...]"
    )


# --- Live security checks ---------------------------------------------------


@pytest.mark.live
def test_kyverno_admission_controller_running(k8s_core_v1) -> None:
    pods = k8s_core_v1.list_namespaced_pod(
        namespace="kyverno",
        label_selector="app.kubernetes.io/component=admission-controller",
    )
    running = [p for p in pods.items if p.status and p.status.phase == "Running"]
    assert running, "No Kyverno admission controller pods Running"


@pytest.mark.live
def test_falco_daemonset_ready(k8s_apps_v1) -> None:
    ds = k8s_apps_v1.read_namespaced_daemon_set(name="falco", namespace="security")
    status = ds.status
    desired = status.desired_number_scheduled or 0
    ready = status.number_ready or 0
    assert desired > 0, "Falco DaemonSet has no desired pods"
    assert ready == desired, f"Falco DaemonSet: {ready}/{desired} Ready"
