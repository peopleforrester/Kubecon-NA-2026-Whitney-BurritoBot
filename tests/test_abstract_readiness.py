# ABOUTME: Static checks on the readiness record against the accepted abstract (issue #75).
# ABOUTME: Every checklist point has a row and a status, cited paths exist, and the CFP draft says it is a draft.

from __future__ import annotations

import re

import pytest

from conftest import PROJECT_ROOT


PRESENTATION_DOCS = PROJECT_ROOT / "presentations" / "kubecon-na-2026" / "docs"
READINESS = PRESENTATION_DOCS / "ABSTRACT-READINESS.md"
CFP = PRESENTATION_DOCS / "CFP-SUBMISSION.md"

# The accepted text: Sessionize session 1249553, transcribed in
# peopleforrester/talks-knowledge abstracts/recovered/sessionize-public-profile.md.
ACCEPTED_SESSION = "1249553"

# The nine points of the checklist in talks-knowledge
# talks/2026-10-16_hard-dated-commitments.md. talks-knowledge#29 (issue #104)
# confirmed each is the same point as the accepted text, in the same order.
CHECKLIST = (
    "Burrito-chain bot",
    "Under-protected MCP server",
    "Full IDP",
    "Starts wide open with live audience hacking",
    "Kubernetes layers",
    "Pre- and mid-inference guardrails",
    "GenAI observability on stage",
    "Ends selling burritos only",
    "Recorded fallback for the live input",
)
STATUSES = ("READY-STATIC", "PARTIAL", "MISSING")

# The accepted wording for the rows that turn on how a point reads,
# quoted from section 5 by talks-knowledge#29 (issue #104).
ACCEPTED_WORDING = {
    "Starts wide open with live audience hacking": (
        "It starts wide open, and we let the audience hack it live",
        "A user does not need to be malicious to embarrass an enterprise, just a little bit weird",
        "Bring your weirdest off-topic question",
    ),
    "Pre- and mid-inference guardrails": (
        "LLM-specific guardrails, like pre- and mid-inference prompt analysis",
    ),
}

# Parts of the checklist's "Ready means" that #75 did not assess; each row
# names what is left to check once the live bring-up (#18) is up.
UNASSESSED = {
    "Kubernetes layers": "before the LLM layer",
    "Recorded fallback for the live input": "venue network",
}
REPO_DIRS = (
    "ai-gateway",
    "apps",
    "deploy",
    "docs",
    "gitops",
    "infrastructure",
    "observability",
    "presentations",
    "scripts",
    "security",
    "tests",
)


def _checklist_rows() -> dict[str, str]:
    """Map each checklist point to its row in the readiness table."""
    rows = {}
    for line in READINESS.read_text(encoding="utf-8").splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if line.startswith("|") and len(cells) >= 3:
            rows[cells[1]] = line
    return rows


@pytest.mark.static
def test_every_checklist_point_has_a_row_with_a_status() -> None:
    """All nine points are assessed, each with exactly one status."""
    assert READINESS.is_file(), f"missing {READINESS}"
    rows = _checklist_rows()
    missing = [p for p in CHECKLIST if p not in rows]
    assert not missing, f"readiness table has no row for: {missing}"
    unrated = [
        p for p in CHECKLIST
        if sum(f"**{s}**" in rows[p] for s in STATUSES) != 1
    ]
    assert not unrated, f"rows without exactly one of {STATUSES}: {unrated}"


@pytest.mark.static
def test_readiness_names_the_accepted_text_and_the_draft() -> None:
    """The record says what it was checked against and that the CFP doc is not it."""
    text = READINESS.read_text(encoding="utf-8")
    assert ACCEPTED_SESSION in text, "readiness record does not name Sessionize session 1249553"
    assert "CFP-SUBMISSION.md" in text, "readiness record does not mention the draft"


def _checked_against() -> str:
    """The record's 'Checked against' paragraph."""
    text = READINESS.read_text(encoding="utf-8")
    start = text.index("**Checked against.**")
    return text[start:text.index("\n\n", start)]


@pytest.mark.static
def test_points_are_checked_against_the_accepted_wording() -> None:
    """The paragraph cites the check (talks-knowledge#29) and no longer says the points are unchecked."""
    paragraph = " ".join(_checked_against().split())
    assert "talks-knowledge#29" in paragraph, "'Checked against' does not cite talks-knowledge#29"
    for caveat in ("no read access", "not checked", "as issue #75 names them"):
        assert caveat not in paragraph, f"'Checked against' still carries the caveat {caveat!r}"


@pytest.mark.static
def test_open_rows_quote_the_accepted_wording() -> None:
    """Rows 4 and 6 quote the accepted text they are rated against."""
    rows = _checklist_rows()
    unquoted = [
        (point, quote)
        for point, quotes in ACCEPTED_WORDING.items()
        for quote in quotes
        if quote not in rows[point]
    ]
    assert not unquoted, f"rows missing the accepted wording: {unquoted}"


@pytest.mark.static
def test_unassessed_ready_means_parts_wait_on_the_live_bring_up() -> None:
    """Rows 5 and 9 name the part not yet assessed and that it waits on #18."""
    rows = _checklist_rows()
    gaps = [
        point for point, part in UNASSESSED.items()
        if part not in rows[point] or "#18" not in rows[point]
    ]
    assert not gaps, f"rows that do not name their unassessed part and #18: {gaps}"


@pytest.mark.static
def test_cited_repo_paths_exist() -> None:
    """Every backticked repo path the record cites as evidence is in the tree."""
    text = READINESS.read_text(encoding="utf-8")
    cited = {
        p.rstrip("/")
        for p in re.findall(r"`([\w./-]+)`", text)
        if p.split("/", 1)[0] in REPO_DIRS and "/" in p
    }
    assert cited, "readiness record cites no repo paths"
    missing = sorted(p for p in cited if not (PROJECT_ROOT / p).exists())
    assert not missing, f"readiness record cites paths that do not exist: {missing}"


@pytest.mark.static
def test_cfp_doc_says_it_is_not_the_accepted_text() -> None:
    """CFP-SUBMISSION.md is an earlier draft; its header points at the accepted session."""
    header = CFP.read_text(encoding="utf-8").split("\n---\n", 1)[0]
    assert "draft" in header.lower(), "CFP-SUBMISSION.md header does not say it is a draft"
    assert ACCEPTED_SESSION in header, "CFP-SUBMISSION.md header does not name the accepted session"
