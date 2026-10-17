# ABOUTME: Phase B7 test — Kyverno install App carries the full EKS-reference values.
# ABOUTME: Asserts webhook namespace exclusions + per-controller resource limits are wired.

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from conftest import PROJECT_ROOT


KYVERNO_APP = PROJECT_ROOT / "gitops" / "apps" / "05-kyverno.yaml"


def _all_docs(path: Path) -> list[dict]:
    with path.open() as fp:
        return [d for d in yaml.safe_load_all(fp) if d]


@pytest.mark.static
def test_kyverno_application_exists() -> None:
    assert KYVERNO_APP.is_file(), f"missing {KYVERNO_APP}"
    doc = _all_docs(KYVERNO_APP)[0]
    assert doc["kind"] == "Application"
    assert doc["metadata"]["name"] == "kyverno"


@pytest.mark.static
def test_kyverno_chart_pinned_and_targets_security() -> None:
    doc = _all_docs(KYVERNO_APP)[0]
    src = doc["spec"]["source"]
    assert src["chart"] == "kyverno"
    assert src.get("targetRevision"), "chart targetRevision must be pinned"
    assert doc["spec"]["destination"]["namespace"] == "security"


@pytest.mark.static
def test_kyverno_webhook_excludes_kube_system_namespaces() -> None:
    """Admission webhook exclusions must exclude system namespaces to avoid lockouts."""
    doc = _all_docs(KYVERNO_APP)[0]
    values = doc["spec"]["source"].get("helm", {}).get("valuesObject", {})
    exprs = (
        values.get("config", {})
        .get("webhooks", {})
        .get("namespaceSelector", {})
        .get("matchExpressions", [])
    )
    found = next(
        (
            e
            for e in exprs
            if e.get("key") == "kubernetes.io/metadata.name"
            and e.get("operator") == "NotIn"
        ),
        None,
    )
    assert found is not None, (
        "kyverno config.webhooks.namespaceSelector must have a NotIn "
        "matchExpression on kubernetes.io/metadata.name (system-namespace "
        "exclusion); otherwise webhook recursion can deadlock the cluster"
    )
    for ns in ("kube-system", "kube-public"):
        assert ns in found["values"], (
            f"system namespace {ns!r} must be in the webhook exclusion list"
        )


@pytest.mark.static
def test_kyverno_controllers_have_resource_limits() -> None:
    """Every Kyverno controller must declare requests + limits — chart defaults are absent."""
    doc = _all_docs(KYVERNO_APP)[0]
    values = doc["spec"]["source"].get("helm", {}).get("valuesObject", {})
    for controller in (
        "admissionController",
        "backgroundController",
        "cleanupController",
        "reportsController",
    ):
        c = values.get(controller, {})
        assert "resources" in c, (
            f"{controller}.resources missing — declare CPU/memory requests "
            f"and limits per Kubernetes best practice"
        )
        assert "requests" in c["resources"] and "limits" in c["resources"], (
            f"{controller}.resources must have both requests and limits"
        )


# Ports the GKE control plane may open to pods on a private-node cluster
# peered by VPC Network Peering: the auto-created "-master" firewall rule
# allows TCP 443 and 10250 only. A webhook on any other port times out.
GKE_CONTROL_PLANE_PORTS = {443, 10250}

# The controllers that serve admission webhooks, the value that sets the
# port they listen on, and the Deployment and container that carry it.
WEBHOOK_SERVERS = {
    "admissionController": ("webhookServer", "kyverno-admission-controller", "kyverno"),
    "cleanupController": ("server", "kyverno-cleanup-controller", "controller"),
}


def _values() -> dict:
    return _all_docs(KYVERNO_APP)[0]["spec"]["source"]["helm"]["valuesObject"]


@pytest.mark.static
def test_kyverno_webhook_ports_are_open_to_the_gke_control_plane() -> None:
    """The chart default of 9443 is closed to the control plane, so admission would time out."""
    values = _values()
    for controller, (key, _, _) in WEBHOOK_SERVERS.items():
        port = values.get(controller, {}).get(key, {}).get("port")
        assert port in GKE_CONTROL_PLANE_PORTS, (
            f"{controller}.{key}.port is {port!r} (chart default 9443); "
            f"the GKE control plane reaches pods only on {sorted(GKE_CONTROL_PLANE_PORTS)}"
        )


@pytest.mark.static
def test_kyverno_webhook_probes_follow_the_moved_port() -> None:
    """The chart's probes hardcode 9443; left there, they fail and restart the pod."""
    values = _values()
    for controller, (key, _, _) in WEBHOOK_SERVERS.items():
        port = values[controller][key]["port"]
        for probe in ("startupProbe", "livenessProbe", "readinessProbe"):
            target = values[controller].get(probe, {}).get("httpGet", {}).get("port")
            assert target in ("https", port), (
                f"{controller}.{probe} probes {target!r} (chart default 9443), "
                f"not the webhook server on {port}"
            )


@pytest.mark.static
def test_kyverno_webhook_network_policies_stay_off() -> None:
    """The chart's webhook NetworkPolicies hardcode 9443 and would drop the moved port."""
    values = _values()
    for controller in WEBHOOK_SERVERS:
        policy = values.get(controller, {}).get("networkPolicy", {})
        assert not policy.get("enabled"), (
            f"{controller}.networkPolicy admits only TCP 9443 in chart 3.7.1; "
            f"enabling it would block the webhook on its moved port"
        )


@pytest.mark.live
def test_kyverno_webhook_containers_listen_on_control_plane_port(k8s_apps_v1) -> None:
    values = _values()
    for controller, (key, deployment, container) in WEBHOOK_SERVERS.items():
        expected = values[controller][key]["port"]
        dep = k8s_apps_v1.read_namespaced_deployment(name=deployment, namespace="security")
        spec = next(c for c in dep.spec.template.spec.containers if c.name == container)
        https = {p.name: p.container_port for p in spec.ports or []}.get("https")
        assert https == expected, (
            f"{deployment}/{container} serves its webhook on {https}, expected {expected}"
        )
