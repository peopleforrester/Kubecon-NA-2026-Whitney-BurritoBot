# ABOUTME: Phase D4 test — gke.tf must not enable Dataplane V2 and legacy Calico together.
# ABOUTME: GKE rejects that combination at apply time; terraform plan cannot catch it.

from __future__ import annotations

import re

import pytest

from conftest import PROJECT_ROOT


GKE_TF = PROJECT_ROOT / "infrastructure" / "terraform" / "gke.tf"


def _uncommented(text: str) -> str:
    return "\n".join(line.split("#", 1)[0] for line in text.splitlines())


def _dataplane_v2_enabled(text: str) -> bool:
    return bool(re.search(r'datapath_provider\s*=\s*"ADVANCED_DATAPATH"', text))


@pytest.mark.static
def test_dataplane_v2_enabled() -> None:
    text = _uncommented(GKE_TF.read_text())
    assert _dataplane_v2_enabled(text), (
        'gke.tf must set datapath_provider = "ADVANCED_DATAPATH" — Dataplane '
        "V2 provides the NetworkPolicy enforcement the Phase 4 policies rely on"
    )


@pytest.mark.static
def test_no_legacy_network_policy_block_with_dataplane_v2() -> None:
    text = _uncommented(GKE_TF.read_text())
    if not _dataplane_v2_enabled(text):
        pytest.fail("Dataplane V2 not enabled; see test_dataplane_v2_enabled")
    assert not re.search(r"(?m)^\s*network_policy\s*{", text), (
        "gke.tf declares a network_policy {} block alongside Dataplane V2. "
        "GKE rejects legacy Calico network policy on an ADVANCED_DATAPATH "
        "cluster at apply time (terraform plan stays green). Remove the block."
    )
    assert not re.search(r'provider\s*=\s*"CALICO"', text), (
        'gke.tf sets provider = "CALICO", which is mutually exclusive with '
        "Dataplane V2"
    )


@pytest.mark.static
def test_no_legacy_network_policy_addon_with_dataplane_v2() -> None:
    text = _uncommented(GKE_TF.read_text())
    if not _dataplane_v2_enabled(text):
        pytest.fail("Dataplane V2 not enabled; see test_dataplane_v2_enabled")
    assert not re.search(r"network_policy_config\s*{", text), (
        "gke.tf declares addons_config.network_policy_config alongside "
        "Dataplane V2. The legacy Calico addon is mutually exclusive with "
        "ADVANCED_DATAPATH and GKE rejects it at apply time. Remove it."
    )
