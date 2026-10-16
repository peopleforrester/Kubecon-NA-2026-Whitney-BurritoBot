# ABOUTME: Phase A4 test — colang_version in nemo-guardrails config must match the
# ABOUTME: actual syntax of the .co rail files. NeMo refuses to load on a mismatch.

from __future__ import annotations

import re

import pytest
import yaml

from conftest import PROJECT_ROOT


CONFIG = PROJECT_ROOT / "ai-gateway" / "nemo-guardrails" / "config.yaml"
RAILS_DIR = PROJECT_ROOT / "ai-gateway" / "nemo-guardrails" / "rails"

# Tokens that only appear in Colang 1.0:
#   - "define user " ... / "define bot " ...
#   - flow ending with "abort"
COLANG_1_PATTERNS = [
    re.compile(r"^\s*define\s+user\s+", re.MULTILINE),
    re.compile(r"^\s*define\s+bot\s+", re.MULTILINE),
]

# Tokens that only appear in Colang 2.x:
#   - "flow user expressed ..."
#   - "user said \"...\""
#   - bare "await"
COLANG_2_PATTERNS = [
    re.compile(r"^\s*flow\s+user\s+expressed\b", re.MULTILINE),
    re.compile(r'^\s*user\s+said\s+"', re.MULTILINE),
    re.compile(r"^\s*await\b", re.MULTILINE),
]


def _detect_rail_syntax() -> str:
    """Return '1.0' or '2.x' based on which patterns dominate the rails."""
    text = "\n".join(p.read_text() for p in RAILS_DIR.glob("*.co"))
    v1_hits = sum(1 for p in COLANG_1_PATTERNS if p.search(text))
    v2_hits = sum(1 for p in COLANG_2_PATTERNS if p.search(text))
    if v1_hits and not v2_hits:
        return "1.0"
    if v2_hits and not v1_hits:
        return "2.x"
    raise AssertionError(
        f"Rail syntax ambiguous: 1.0 hits={v1_hits}, 2.x hits={v2_hits}"
    )


@pytest.mark.static
def test_colang_version_matches_rail_syntax() -> None:
    """If config declares one version but rails are written in the other, NeMo dies."""
    cfg = yaml.safe_load(CONFIG.read_text())
    declared = str(cfg.get("colang_version", "")).strip()
    actual = _detect_rail_syntax()
    assert declared == actual, (
        f"config.yaml declares colang_version={declared!r} but rails are "
        f"written in Colang {actual} syntax. NeMo Guardrails will refuse "
        f"to load on this mismatch — pick one and align."
    )
