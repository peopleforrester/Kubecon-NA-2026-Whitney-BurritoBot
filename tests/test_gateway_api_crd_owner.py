# ABOUTME: The Gateway API CRDs have exactly one owner (#97): GKE (gateway_api_config, #111) at a GKE version whose
# ABOUTME: bundle serves the manifests, or the envoy-gateway-crds Application if GKE's Gateway API is turned off.

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml
from test_gateway_api_floor import required_floor

from conftest import PROJECT_ROOT
from helpers.gateway_api_crds import (
    GKE_GATEWAY_API_BUNDLES,
    Files,
    gke_bundle_for,
    gke_floor_for,
    gke_manages_gateway_api,
    gke_min_master_version,
    load_files,
    owner_problems,
)
from helpers.manifest_graph import GATEWAY_API, load_manifests


GITOPS_APPS = PROJECT_ROOT / "gitops" / "apps"
NAMESPACES_APP = GITOPS_APPS / "00-namespaces.yaml"
EG_APP = GITOPS_APPS / "envoy-gateway.yaml"
EG_CRDS_APP = GITOPS_APPS / "envoy-gateway-crds.yaml"
EG_CRDS_REL = str(EG_CRDS_APP.relative_to(PROJECT_ROOT))
EG_REL = str(EG_APP.relative_to(PROJECT_ROOT))
GKE_TF = "infrastructure/terraform/gke.tf"
GKE_CHANNEL = re.compile(r'(  gateway_api_config \{\n    channel = ")([A-Z_]+)("\n  \}\n)')
GKE_MIN_VERSION = re.compile(r'(  min_master_version = ")([^"]+)("\n)')

FILES = load_files(PROJECT_ROOT)
# The oldest Gateway API release that serves every Gateway API object the
# manifests apply (BackendTLSPolicy v1 -> v1.4, tests/test_gateway_api_floor.py).
FLOOR = required_floor(load_manifests(PROJECT_ROOT))


def _app(path: Path) -> dict:
    assert path.is_file(), f"missing {path.relative_to(PROJECT_ROOT)}"
    (app,) = [d for d in yaml.safe_load_all(path.read_text(encoding="utf-8")) if d and d.get("kind") == "Application"]
    return app


def _source(path: Path) -> dict:
    return _app(path)["spec"]["source"]


def _crds_values(path: Path) -> dict:
    return _source(path)["helm"]["valuesObject"]["crds"]


def _wave(path: Path) -> int:
    return int(_app(path)["metadata"]["annotations"]["argocd.argoproj.io/sync-wave"])


# --- the repo as it stands --------------------------------------------------


@pytest.mark.static
def test_gateway_api_crds_have_exactly_one_owner() -> None:
    assert owner_problems(FILES, FLOOR) == []


@pytest.mark.static
def test_gke_owns_the_gateway_api_crds_at_its_newest_bundle() -> None:
    """Question 206 (#111): GKE's Gateway API, off the Envoy Gateway v1.9 matrix
    (Gateway API v1.6.1), at the closest bundle GKE ships (v1.5.0)."""
    assert gke_manages_gateway_api(FILES)
    assert _crds_values(EG_CRDS_APP)["gatewayAPI"]["enabled"] is False
    assert gke_min_master_version(FILES) == GKE_GATEWAY_API_BUNDLES[0][0]


@pytest.mark.static
def test_envoy_gateway_chart_installs_no_crds() -> None:
    """gateway-helm's crds subchart carries the Gateway API CRDs (experimental
    channel) and the Envoy Gateway CRDs; both move to envoy-gateway-crds."""
    assert _crds_values(EG_APP)["enabled"] is False


@pytest.mark.static
def test_crds_app_installs_the_envoy_gateway_crds() -> None:
    """Backend, EnvoyProxy and EnvoyExtensionPolicy (gateway.envoyproxy.io) are
    Envoy Gateway's own; no provider installs them."""
    assert _crds_values(EG_CRDS_APP)["envoyGateway"]["enabled"] is True


@pytest.mark.static
def test_crds_chart_is_the_envoy_gateway_release() -> None:
    crds, controller = _source(EG_CRDS_APP), _source(EG_APP)
    assert (crds["repoURL"], crds["chart"]) == ("docker.io/envoyproxy", "gateway-crds-helm")
    assert crds["targetRevision"] == controller["targetRevision"], "CRDs and controller must move together"


@pytest.mark.static
def test_crds_sync_before_envoy_gateway_starts() -> None:
    """Envoy Gateway looks up which optional CRDs exist once, at startup: with no
    BackendTLSPolicy v1 it logs "skipping BackendTLSPolicy watch" and the Vertex
    AI upstream loses its TLS policy until the pod restarts (v1.9.2
    internal/provider/kubernetes/controller.go)."""
    assert _wave(NAMESPACES_APP) < _wave(EG_CRDS_APP) < _wave(EG_APP)


@pytest.mark.static
def test_chart_gateway_api_channel_is_the_one_gke_serves() -> None:
    """GKE installs only the standard channel. Should the chart take the CRDs
    back, it renders the same channel, so an experimental-only field cannot
    pass there and be dropped on GKE."""
    assert _crds_values(EG_CRDS_APP)["gatewayAPI"]["channel"] == "standard"


@pytest.mark.static
def test_every_gateway_api_object_is_in_the_floor_bundle() -> None:
    """The floor is computed from the manifests; this proves there are some."""
    kinds = {m.kind for m in load_manifests(PROJECT_ROOT) if m.group == GATEWAY_API}
    assert {"Gateway", "BackendTLSPolicy"} <= kinds
    assert FLOOR == "1.4"


# --- the GKE version table ----------------------------------------------------


@pytest.mark.static
@pytest.mark.parametrize(
    "version,bundle",
    [
        ("1.35.2-gke.1842000", "1.5"),
        ("1.36.0-gke.1000", "1.5"),
        ("1.35.2-gke.1841999", "1.4"),
        ("1.34.1-gke.1822000", "1.4"),
        ("1.34.1-gke.1821999", "1.3"),
        ("1.34", "1.3"),
        ("1.33.2-gke.1335000", "1.3"),
        ("1.30.1", None),
    ],
)
def test_gke_bundle_for(version: str, bundle: str | None) -> None:
    assert gke_bundle_for(version) == bundle


@pytest.mark.static
def test_gke_floor_serves_backend_tls_policy_v1() -> None:
    assert gke_floor_for(FLOOR) == "1.34.1-gke.1822000"
    assert GKE_GATEWAY_API_BUNDLES[0] == ("1.35.2-gke.1842000", "1.5"), "newest GKE bundle changed; re-read the table"


# --- mutation tests: the flip, and each way to get it wrong -------------------


def _set_terraform(files: Files, pattern: re.Pattern[str], value: str) -> None:
    """Set the value pattern matches in gke.tf, or drop the whole match for ""."""
    text, count = pattern.subn(lambda m: m[1] + value + m[3] if value else "", files[GKE_TF])
    assert count == 1, f"{pattern.pattern} moved in {GKE_TF}; update the mutation anchor"
    files[GKE_TF] = text


def _mutate(
    *,
    gke_channel: str | None = None,
    min_master_version: str | None = None,
    chart_gateway_api: bool | None = None,
    eg_chart_crds: bool | None = None,
) -> Files:
    """The repo's files with each given setting changed; None leaves it as it
    stands, and "" removes gateway_api_config or min_master_version."""
    files = dict(FILES)
    if gke_channel is not None:
        _set_terraform(files, GKE_CHANNEL, gke_channel)
    if min_master_version is not None:
        _set_terraform(files, GKE_MIN_VERSION, min_master_version)
    if chart_gateway_api is not None:
        current = _crds_values(EG_CRDS_APP)["gatewayAPI"]["enabled"]
        old = f"gatewayAPI:\n            enabled: {str(current).lower()}"
        assert old in files[EG_CRDS_REL], "crds.gatewayAPI.enabled moved; update the mutation anchor"
        files[EG_CRDS_REL] = files[EG_CRDS_REL].replace(
            old, f"gatewayAPI:\n            enabled: {str(chart_gateway_api).lower()}", 1
        )
    if eg_chart_crds is not None:
        old = "crds:\n          enabled: false"
        assert old in files[EG_REL], "gateway-helm crds.enabled moved; update the mutation anchor"
        files[EG_REL] = files[EG_REL].replace(old, f"crds:\n          enabled: {str(eg_chart_crds).lower()}", 1)
    return files


@pytest.mark.static
@pytest.mark.parametrize("min_master_version", ["1.34.1-gke.1822000", "1.35.2-gke.1842000", "1.36.1-gke.1000"])
def test_mutation_any_floor_from_the_bundle_that_serves_the_manifests_is_clean(min_master_version: str) -> None:
    files = _mutate(min_master_version=min_master_version)
    assert gke_manages_gateway_api(files)
    assert owner_problems(files, FLOOR) == []


@pytest.mark.static
def test_mutation_the_flip_back_is_clean() -> None:
    """Handing the CRDs back to envoy-gateway-crds (#97's shape): gateway_api_config
    and its version floor out, the chart's Gateway API CRDs on, in one change."""
    files = _mutate(gke_channel="", min_master_version="", chart_gateway_api=True)
    assert not gke_manages_gateway_api(files)
    assert owner_problems(files, FLOOR) == []


MUTATIONS = {
    "gke-on-chart-back-on": (
        {"chart_gateway_api": True},
        "exactly one owner, found 2",
    ),
    "gke-on-no-version-floor": (
        {"min_master_version": ""},
        "min_master_version is unset",
    ),
    "gke-on-v1.3-bundle": (
        {"min_master_version": "1.33.5-gke.1000"},
        "installs Gateway API v1.3",
    ),
    "gke-on-short-version": (
        {"min_master_version": "1.34"},
        "installs Gateway API v1.3",
    ),
    "gke-on-below-table": (
        {"min_master_version": "1.29.4"},
        "older than the table",
    ),
    "gke-off-chart-off": (
        {"gke_channel": "", "min_master_version": ""},
        "exactly one owner, found 0",
    ),
    "gke-disabled-chart-off": (
        {"gke_channel": "CHANNEL_DISABLED"},
        "exactly one owner, found 0",
    ),
    "envoy-gateway-chart-crds-back-on": (
        {"eg_chart_crds": True},
        "exactly one owner, found 2",
    ),
}


@pytest.mark.static
@pytest.mark.parametrize("name", MUTATIONS)
def test_mutation_is_reported(name: str) -> None:
    changes, expected = MUTATIONS[name]
    problems = owner_problems(_mutate(**changes), FLOOR)
    assert len(problems) == 1 and expected in problems[0], problems


# --- live: the cluster's Gateway API CRDs come from one bundle ----------------


@pytest.mark.live
def test_installed_gateway_api_crds_come_from_one_bundle(k8s_apiextensions_v1) -> None:
    crds = [
        crd
        for crd in k8s_apiextensions_v1.list_custom_resource_definition().items
        if crd.spec.group == GATEWAY_API
    ]
    assert crds, f"no {GATEWAY_API} CRDs installed"
    bundles = {
        crd.metadata.name: (
            (crd.metadata.annotations or {}).get(f"{GATEWAY_API}/bundle-version"),
            (crd.metadata.annotations or {}).get(f"{GATEWAY_API}/channel"),
        )
        for crd in crds
    }
    assert len(set(bundles.values())) == 1, f"Gateway API CRDs from more than one bundle: {bundles}"
    ((version, channel),) = set(bundles.values())
    assert channel == "standard", f"Gateway API CRDs are {channel}, the repo expects standard: {bundles}"
    release = version.removeprefix("v").split(".")[:2]
    assert tuple(int(p) for p in release) >= tuple(int(p) for p in FLOOR.split(".")), (
        f"installed Gateway API {version} is below the manifests' v{FLOOR}"
    )
