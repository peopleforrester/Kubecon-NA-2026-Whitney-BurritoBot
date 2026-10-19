# ABOUTME: Static checks on the decisions.md entry for question 163 (issue #95): its answer, who decided, and what it changes.
# ABOUTME: Fails when the entry is missing or duplicated, loses answer A or the standing-rules sentence, or claims Michael approved (issue #123).

from __future__ import annotations

import re

import pytest

from conftest import PROJECT_ROOT


DECISIONS = PROJECT_ROOT / "decisions.md"
DECIDED_BY = "Decided by hecaton's research under Michael's standing rules, not by Michael."
HEADING = re.compile(r"^## .*\bquestion 163\b.*$", re.MULTILINE)
NEXT_HEADING = re.compile(r"^## ", re.MULTILINE)
MICHAEL_APPROVED = re.compile(
    r"\b(?:approved|confirmed|decided|signed off|agreed)\s+by\s+Michael\b"
    r"|\bMichael\s+(?:approved|confirmed|decided|signed off|agreed|chose|picked)\b"
    r"|\bPer\s+Michael\b"
    r"|\bon\s+Michael's\s+(?:instruction|approval|answer|ask)\b",
    re.IGNORECASE,
)


def _entry() -> tuple[str, str]:
    """Return the question 163 entry's heading and its whitespace-normalised body."""
    text = DECISIONS.read_text(encoding="utf-8")
    headings = list(HEADING.finditer(text))
    assert len(headings) == 1, (
        f"decisions.md has {len(headings)} entries naming question 163; expected exactly one: "
        f"{[m.group(0) for m in headings]}"
    )
    start = headings[0].end()
    following = NEXT_HEADING.search(text, start)
    body = text[start:following.start() if following else len(text)]
    return headings[0].group(0), re.sub(r"\s+", " ", body)


@pytest.mark.static
def test_question_163_entry_names_question_and_issue() -> None:
    """One decisions.md entry names question 163 and issue #95 in its heading."""
    heading, _ = _entry()
    assert re.search(r"#95\b", heading), f"the question 163 entry heading does not name #95: {heading!r}"
    assert "decision" in heading, f"the question 163 entry is not a decision entry: {heading!r}"


@pytest.mark.static
def test_question_163_entry_states_answer_a() -> None:
    """The entry states answer A: drop the guarded KSA's WIF annotation and workload_wif_binding."""
    _, body = _entry()
    assert "Answer: A." in body, "the question 163 entry does not state 'Answer: A.'"
    answer = body.split("Answer: A.", 1)[1]
    for needed in ("iam.gke.io/gcp-service-account", "workload_wif_binding", "iam.tf"):
        assert needed in answer, f"answer A in the question 163 entry does not name {needed!r}"


@pytest.mark.static
def test_question_163_entry_says_who_decided() -> None:
    """The entry carries the exact standing-rules sentence and claims no approval by Michael."""
    _, body = _entry()
    assert DECIDED_BY in body, f"the question 163 entry lacks the sentence {DECIDED_BY!r}"
    claims = [m.group(0) for m in MICHAEL_APPROVED.finditer(body.replace(DECIDED_BY, ""))]
    assert not claims, f"the question 163 entry claims Michael approved it: {claims}"


@pytest.mark.static
def test_question_163_entry_says_what_it_changes() -> None:
    """The entry lists what answer A changes: the guarded SA manifest, the A2 test, iam.tf and the GSA."""
    _, body = _entry()
    assert "What it changes" in body, "the question 163 entry has no 'What it changes' part"
    changes = body.split("What it changes", 1)[1]
    for needed in (
        "apps/burritbot/k8s/serviceaccount-burritbot-guarded.yaml",
        "tests/test_critical_fix_a2_service_accounts.py",
        "test_burritbot_guarded_sa_has_no_wif_annotation",
        "workload_wif_binding",
        "burritbot-workload",
    ):
        assert needed in changes, f"the question 163 entry's changes do not name {needed!r}"
