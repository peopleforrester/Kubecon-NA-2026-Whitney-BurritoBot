# ABOUTME: Static checks that event state lives in conference-knowledge, not in this repo.
# ABOUTME: The CFP doc and AGENTS.md point there instead of keeping their own copy (issue #36).

from __future__ import annotations

import re

import pytest

from conftest import PROJECT_ROOT


CFP = PROJECT_ROOT / "presentations" / "kubecon-na-2026" / "docs" / "CFP-SUBMISSION.md"
AGENTS = PROJECT_ROOT / "AGENTS.md"
SOURCE = "peopleforrester/conference-knowledge"

# Header fields that are event state: conference-knowledge owns them.
EVENT_STATE_FIELDS = ("Location", "Dates", "CFP Deadline", "Submission Platform")


@pytest.mark.static
def test_cfp_doc_keeps_no_copy_of_event_state() -> None:
    """The CFP header names the event but leaves dates and deadlines to conference-knowledge."""
    text = CFP.read_text(encoding="utf-8")
    copied = [f for f in EVENT_STATE_FIELDS if re.search(rf"^\*\*{f}:\*\*", text, re.MULTILINE)]
    assert not copied, f"CFP-SUBMISSION.md still carries event state: {copied}"
    assert SOURCE in text, f"CFP-SUBMISSION.md does not point at {SOURCE}"


@pytest.mark.static
def test_agents_md_says_where_conference_information_lives() -> None:
    """AGENTS.md has a 'Where things live' section naming conference-knowledge."""
    text = AGENTS.read_text(encoding="utf-8")
    match = re.search(r"^## Where things live\b(.*?)(?=^## |\Z)", text, re.MULTILINE | re.DOTALL)
    assert match, "AGENTS.md has no '## Where things live' section"
    assert SOURCE in match.group(1), f"'Where things live' does not name {SOURCE}"
