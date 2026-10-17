# ABOUTME: Static checks on the working copy of spec 001 (issue #114): it names its source and sha256,
# ABOUTME: its spec text is the delivered file byte for byte bar Corrections, and its milestone status follows the spec.

from __future__ import annotations

import hashlib
import re
from collections.abc import Callable

import pytest

from conftest import PROJECT_ROOT


WORKING_COPY = PROJECT_ROOT / "specs" / "001-ready-by-11-08-delivered-11-12.md"
PROJECT_STATE = PROJECT_ROOT / "PROJECT_STATE.md"

# Named by issue #114: the delivered file in personal-knowledge and its hash.
SOURCE_PATH = "specs/talks/burritobot/001-ready-by-11-08-delivered-11-12.md"
SOURCE_SHA256 = "fdc5f0742d9e2f6235178bcada13da9ee875dae64072cfe8f6633ecc04ee2d16"

BEGIN = "<!-- BEGIN SPEC 001 -->\n"
END = "<!-- END SPEC 001 -->"
CORRECTIONS = "\n## Corrections\n"
# The delivered file's Corrections section, which the hash covers.
DELIVERED_CORRECTIONS = "\nNone yet.\n"

STATUSES = ("DONE", "OPEN", "WAITING")
MILESTONES = tuple(f"M{n}" for n in range(1, 10))


def _split(text: str) -> tuple[str, str]:
    """Return (working-copy header, spec text between the markers)."""
    assert BEGIN in text, f"working copy has no {BEGIN.strip()} marker"
    header, rest = text.split(BEGIN, 1)
    assert END in rest, f"working copy has no {END} marker"
    return header, rest.split(END, 1)[0]


def _as_delivered(spec: str) -> str:
    """The spec text with its Corrections section put back as delivered."""
    head, sep, _ = spec.partition(CORRECTIONS)
    assert sep, "the spec text has no '## Corrections' section"
    return head + sep + DELIVERED_CORRECTIONS


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _table(text: str, heading: str) -> list[list[str]]:
    """Rows of the first Markdown table under `heading`, cells stripped, header and rule dropped."""
    assert heading in text, f"no '{heading}' section"
    section = text.split(heading, 1)[1].split("\n## ", 1)[0]
    lines = [ln for ln in section.splitlines() if ln.startswith("|")]
    assert len(lines) > 2, f"'{heading}' has no table"
    return [[c.strip() for c in ln.strip().strip("|").split("|")] for ln in lines[2:]]


@pytest.mark.static
def test_working_copy_names_source_and_sha256() -> None:
    header, _ = _split(WORKING_COPY.read_text())
    assert "personal-knowledge" in header and SOURCE_PATH in header, (
        "the working copy's header must name its source, personal-knowledge "
        f"`{SOURCE_PATH}`"
    )
    assert SOURCE_SHA256 in header, "the working copy's header must name the source sha256"
    assert "#114" in header, "the working copy's header must name issue #114"


@pytest.mark.static
def test_spec_text_is_the_delivered_file() -> None:
    """Between the markers, bar Corrections, the text hashes to the delivered sha256."""
    _, spec = _split(WORKING_COPY.read_text())
    assert _sha256(_as_delivered(spec)) == SOURCE_SHA256, (
        "the spec text in the working copy no longer matches the delivered "
        "file. Only its Corrections section may change here; changes to the "
        "spec go back to personal-knowledge as an issue."
    )


def _add_correction(spec: str) -> str:
    return spec.replace(
        CORRECTIONS + DELIVERED_CORRECTIONS,
        CORRECTIONS + "\n- 2026-10-18: a correction.\n",
    )


def _move_a_date(spec: str) -> str:
    return spec.replace("**2026-10-23**", "**2026-10-24**", 1)


def _drop_a_milestone(spec: str) -> str:
    return re.sub(r"^\| M5 \|.*\n", "", spec, count=1, flags=re.MULTILINE)


@pytest.mark.static
@pytest.mark.parametrize(
    ("mutate", "still_delivered"),
    [(_add_correction, True), (_move_a_date, False), (_drop_a_milestone, False)],
    ids=["correction-allowed", "moved-date", "dropped-milestone"],
)
def test_hash_check_allows_only_corrections(
    mutate: Callable[[str], str], still_delivered: bool
) -> None:
    _, spec = _split(WORKING_COPY.read_text())
    mutated = mutate(spec)
    assert mutated != spec, "the mutation did not change the spec text"
    assert (_sha256(_as_delivered(mutated)) == SOURCE_SHA256) is still_delivered


@pytest.mark.static
def test_milestone_status_follows_the_spec() -> None:
    """One status row per spec milestone, closing with the KR or metric the spec says it moves."""
    header, spec = _split(WORKING_COPY.read_text())
    spec_rows = {r[0]: r for r in _table(spec, "## Milestones")}
    assert tuple(spec_rows) == MILESTONES, f"spec milestones are {tuple(spec_rows)}"

    status_rows = _table(header, "## Milestone status")
    assert tuple(r[0] for r in status_rows) == MILESTONES, (
        "the status table must list M1 to M9 in order"
    )
    for row in status_rows:
        assert len(row) == 6, f"{row[0]}: expected 6 cells, got {row}"
        milestone, due, status, closes_with, waits_on, where = row
        _, _, spec_moves, spec_date = spec_rows[milestone]
        assert due == spec_date.replace("**", ""), (
            f"{milestone}: due {due!r}, the spec says {spec_date!r}"
        )
        assert closes_with == spec_moves, (
            f"{milestone}: closes with {closes_with!r}, the spec says it moves {spec_moves!r}"
        )
        assert status in STATUSES, f"{milestone}: status {status!r} not in {STATUSES}"
        if status == "WAITING":
            assert re.search(r"#\d+|\bM\d\b|\d{4}-\d{2}-\d{2}", waits_on), (
                f"{milestone}: WAITING must name the issue, milestone or date it waits on"
            )
        if status == "DONE":
            assert re.search(r"\b[0-9a-f]{7,40}\b|#\d+", where), (
                f"{milestone}: DONE must cite the commit or issue that closed it"
            )
        assert where, f"{milestone}: say where it stands"


@pytest.mark.static
def test_project_state_points_to_the_working_copy() -> None:
    open_work = PROJECT_STATE.read_text().split("## Open Work", 1)
    assert len(open_work) == 2, "PROJECT_STATE.md has no '## Open Work' section"
    assert "specs/001-ready-by-11-08-delivered-11-12.md" in open_work[1].split("\n## ", 1)[0], (
        "PROJECT_STATE.md's Open Work must point to the spec 001 working copy"
    )
