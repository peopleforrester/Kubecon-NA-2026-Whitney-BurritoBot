# ABOUTME: Phase D4 test — gke.tf must enable Dataplane V2 for native NetworkPolicy enforcement.
# ABOUTME: Its exclusion of legacy Calico is asserted in test_incompatible_settings.py.

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
