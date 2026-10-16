# ABOUTME: Static checks that decision entries live in the append-only decisions.md, not PROJECT_STATE.md.
# ABOUTME: Covers the carried-over 2026-10-15 promote entry and the AGENTS.md rule for new ones (issue #47).

from __future__ import annotations

import re

import pytest

from conftest import PROJECT_ROOT


STATE = PROJECT_ROOT / "PROJECT_STATE.md"
DECISIONS = PROJECT_ROOT / "decisions.md"
AGENTS = PROJECT_ROOT / "AGENTS.md"
ENTRY_HEADING = re.compile(r"^## \d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z · ", re.MULTILINE)
PROMOTE_HEADING = "## 2026-10-15T12:00:00Z · 3.3 · Main fast-forwarded with known test failures"


@pytest.mark.static
def test_state_file_holds_no_decision_entries() -> None:
    """PROJECT_STATE.md has no '## <timestamp> · ...' decision-entry headings."""
    stray = ENTRY_HEADING.findall(STATE.read_text(encoding="utf-8"))
    assert not stray, f"PROJECT_STATE.md holds decision entries; append them to decisions.md: {stray}"


@pytest.mark.static
def test_promote_entry_carried_into_decisions_log() -> None:
    """The 2026-10-15 promote entry sits in decisions.md with its original heading and body."""
    text = DECISIONS.read_text(encoding="utf-8")
    assert PROMOTE_HEADING in text, "decisions.md lacks the 2026-10-15 promote entry"
    entry = text.split(PROMOTE_HEADING, 1)[1]
    for needed in ("On Michael's instruction", "test_terraform_plan", "invalid_grant"):
        assert needed in entry, f"carried-over promote entry lacks {needed!r}"


@pytest.mark.static
def test_agents_md_sends_decision_entries_to_decisions_log() -> None:
    """Session Discipline says decision entries, promote-time ones included, append to decisions.md."""
    match = re.search(r"^## Session Discipline\b(.*?)(?=^## |\Z)", AGENTS.read_text(encoding="utf-8"),
                      re.MULTILINE | re.DOTALL)
    assert match, "no '## Session Discipline' section in AGENTS.md"
    section = re.sub(r"\s+", " ", match.group(1))
    assert "decisions.md" in section, "Session Discipline does not name decisions.md"
    assert "promote" in section, "Session Discipline does not cover promote-time entries"
