# ABOUTME: Known-incompatible setting pairs, asserted apart — each entry records why the two cannot coexist.
# ABOUTME: Mutation tests add the missing half of every pair to the real files and confirm it is reported.

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass

import pytest

from conftest import PROJECT_ROOT
from helpers.gateway_api_crds import (
    Files,
    applications,
    gateway_api_chart_owners,
    gke_manages_gateway_api,
    load_files,
)
from helpers.gateway_api_crds import terraform_text as _terraform


def _helm_charts(files: Files) -> set[str]:
    """Charts installed by the ArgoCD Applications under gitops/apps."""
    charts: set[str] = set()
    for _, app in applications(files):
        spec = app["spec"]
        for source in [spec.get("source") or {}, *(spec.get("sources") or [])]:
            if "chart" in source:
                charts.add(source["chart"])
    return charts


@dataclass(frozen=True)
class Setting:
    description: str
    holds: Callable[[Files], bool]


@dataclass(frozen=True)
class IncompatiblePair:
    a: Setting
    b: Setting
    reason: str


DATAPLANE_V2 = Setting(
    'GKE Dataplane V2 (datapath_provider = "ADVANCED_DATAPATH")',
    lambda f: bool(re.search(r'datapath_provider\s*=\s*"ADVANCED_DATAPATH"', _terraform(f))),
)
LEGACY_NETWORK_POLICY = Setting(
    'legacy Calico network_policy {} block or provider = "CALICO"',
    lambda f: bool(
        re.search(r"(?m)^\s*network_policy\s*{", _terraform(f))
        or re.search(r'provider\s*=\s*"CALICO"', _terraform(f))
    ),
)
NETWORK_POLICY_ADDON = Setting(
    "addons_config.network_policy_config (legacy Calico addon)",
    lambda f: bool(re.search(r"network_policy_config\s*{", _terraform(f))),
)
AUTOPILOT = Setting(
    "GKE Autopilot (enable_autopilot = true)",
    lambda f: bool(re.search(r"enable_autopilot\s*=\s*true", _terraform(f))),
)
FALCO_DAEMONSET = Setting(
    "Falco chart (privileged DaemonSet) in gitops/apps",
    lambda f: "falco" in _helm_charts(f),
)
GKE_GATEWAY_API = Setting(
    "GKE-managed Gateway API CRDs (gateway_api_config with a channel other than CHANNEL_DISABLED)",
    gke_manages_gateway_api,
)
EG_GATEWAY_API_CRDS = Setting(
    "an Envoy Gateway chart installing the Gateway API CRDs in gitops/apps "
    "(gateway-helm crds.enabled or gateway-crds-helm crds.gatewayAPI.enabled)",
    lambda f: bool(gateway_api_chart_owners(f)),
)

INCOMPATIBLE: dict[str, IncompatiblePair] = {
    # #22: terraform plan stays green; the GKE API rejects it at apply.
    "dataplane-v2-vs-calico-policy": IncompatiblePair(
        DATAPLANE_V2,
        LEGACY_NETWORK_POLICY,
        "Dataplane V2 enforces NetworkPolicy itself; GKE refuses legacy Calico "
        "network policy on an ADVANCED_DATAPATH cluster at apply time.",
    ),
    "dataplane-v2-vs-calico-addon": IncompatiblePair(
        DATAPLANE_V2,
        NETWORK_POLICY_ADDON,
        "The network_policy_config addon installs legacy Calico, which GKE "
        "refuses alongside ADVANCED_DATAPATH at apply time.",
    ),
    # CLAUDE.md architecture decision: GKE Standard, not Autopilot.
    "autopilot-vs-falco": IncompatiblePair(
        AUTOPILOT,
        FALCO_DAEMONSET,
        "Autopilot forbids privileged containers; the Falco DaemonSet needs "
        "them for its modern-eBPF driver.",
    ),
    # #68, #97: Envoy Gateway's gateway-crds-helm README: where the provider
    # manages the Gateway API CRDs, leave the chart's copy off rather than mix
    # two copies.
    "gke-gateway-api-vs-envoy-gateway-crds": IncompatiblePair(
        GKE_GATEWAY_API,
        EG_GATEWAY_API_CRDS,
        "GKE owns the Gateway API CRDs and reconciles its own version and "
        "channel over any copy ArgoCD applies from a chart. Handing them back "
        "to envoy-gateway-crds (crds.gatewayAPI.enabled true) turns "
        "gateway_api_config off in the same change "
        "(tests/test_gateway_api_crd_owner.py).",
    ),
}

FILES = load_files(PROJECT_ROOT)


def _violations(files: Files) -> list[str]:
    return [
        f"{name}: {pair.a.description} + {pair.b.description} — {pair.reason}"
        for name, pair in INCOMPATIBLE.items()
        if pair.a.holds(files) and pair.b.holds(files)
    ]


@pytest.mark.static
def test_no_incompatible_pair_is_set() -> None:
    violations = _violations(FILES)
    assert not violations, "incompatible settings:\n  " + "\n  ".join(violations)


@pytest.mark.static
@pytest.mark.parametrize(
    "setting", [DATAPLANE_V2, FALCO_DAEMONSET, GKE_GATEWAY_API], ids=lambda s: s.description
)
def test_enabled_half_is_still_detected(setting: Setting) -> None:
    """Each pair has one half the repo relies on; if its detector goes blind
    (file moved, syntax changed) the pair could never fire."""
    assert setting.holds(FILES), f"{setting.description} not detected in the repo"


# --- mutation tests: add the missing half, confirm the pair is reported ----

GKE_TF = "infrastructure/terraform/gke.tf"
CLUSTER_OPEN = 'resource "google_container_cluster" "burritbot" {\n'
GKE_GATEWAY_API_ON = '  gateway_api_config {\n    channel = "CHANNEL_STANDARD"\n  }\n'


def _replace(files: Files, path: str, old: str, new: str) -> Files:
    files = dict(files)
    assert files[path].count(old) == 1, f"{old!r} moved in {path}; update the mutation anchor"
    files[path] = files[path].replace(old, new, 1)
    return files


def _inject_into_cluster(snippet: str) -> Files:
    return _replace(FILES, GKE_TF, CLUSTER_OPEN, CLUSTER_OPEN + snippet)


def _eg_crds_gateway_api_on() -> Files:
    return _replace(
        FILES,
        "gitops/apps/envoy-gateway-crds.yaml",
        "gatewayAPI:\n            enabled: false",
        "gatewayAPI:\n            enabled: true",
    )


def _gateway_helm_crds_on() -> Files:
    return _replace(FILES, "gitops/apps/envoy-gateway.yaml", "crds:\n          enabled: false", "crds:\n          enabled: true")


MUTATIONS: dict[str, dict[str, Callable[[], Files]]] = {
    "dataplane-v2-vs-calico-policy": {
        # #22 as shipped.
        "calico-provider": lambda: _inject_into_cluster(
            "  network_policy {\n    enabled  = true\n    provider = \"CALICO\"\n  }\n"
        ),
        "network-policy-block": lambda: _inject_into_cluster("  network_policy {\n    enabled = false\n  }\n"),
    },
    "dataplane-v2-vs-calico-addon": {
        "addon": lambda: _inject_into_cluster(
            "  addons_config {\n    network_policy_config {\n      disabled = false\n    }\n  }\n"
        ),
    },
    "autopilot-vs-falco": {
        "autopilot": lambda: _inject_into_cluster("  enable_autopilot = true\n"),
    },
    # GKE's Gateway API is on (#111); the missing half is a chart's copy.
    "gke-gateway-api-vs-envoy-gateway-crds": {
        "gateway-crds-helm": _eg_crds_gateway_api_on,
        "gateway-helm": _gateway_helm_crds_on,
    },
}


@pytest.mark.static
def test_every_pair_has_a_mutation() -> None:
    assert MUTATIONS.keys() == INCOMPATIBLE.keys()


@pytest.mark.static
@pytest.mark.parametrize(
    "pair,case",
    [(pair, case) for pair, cases in MUTATIONS.items() for case in cases],
)
def test_mutation_is_reported(pair: str, case: str) -> None:
    violations = _violations(MUTATIONS[pair][case]())
    assert any(v.startswith(f"{pair}:") for v in violations), violations


@pytest.mark.static
def test_mutation_in_a_comment_is_ignored() -> None:
    violations = _violations(_inject_into_cluster("  # network_policy {\n  # enable_autopilot = true\n"))
    assert violations == []


@pytest.mark.static
def test_disabled_gke_gateway_api_is_not_reported() -> None:
    disabled = GKE_GATEWAY_API_ON.replace("STANDARD", "DISABLED")
    files = _replace(_eg_crds_gateway_api_on(), GKE_TF, GKE_GATEWAY_API_ON, disabled)
    assert not GKE_GATEWAY_API.holds(files)
    assert _violations(files) == []
