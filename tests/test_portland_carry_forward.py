# ABOUTME: Static checks that the Portland workshop results are carried into this talk's docs.
# ABOUTME: Covers the carry-forward map, night-before provisioning, rule-on-screen, and measurements.

from __future__ import annotations

import datetime as dt
import re

import pytest

from conftest import PROJECT_ROOT


PRESENTATION_DOCS = PROJECT_ROOT / "presentations" / "kubecon-na-2026" / "docs"
CARRY_FORWARD = PRESENTATION_DOCS / "PORTLAND-CARRY-FORWARD.md"
RUNBOOK = PRESENTATION_DOCS / "RUNBOOK.md"

# First day of the event. peopleforrester/conference-knowledge
# (events/registry.yaml) owns this date; follow it there if it moves.
# Portland's cold read landed inside the last
# 72 hours by luck; the scheduled one must sit well clear of that.
EVENT_START = dt.date(2026, 11, 9)
COLD_READ_MIN_LEAD_DAYS = 7

PROVEN_ITEMS = (
    "Hands-on format",
    "Denial of wallet",
    "Step zero",
    "Real policy YAML",
    "Provision the night before",
    "Feedback button",
)
UNMEASURED_ITEMS = (
    "Per-segment timing",
    "Mobile",
    "Room network",
    "Cost",
)
SEGMENTS = ("Pre-flight", "Act 1", "Cast the Net", "Act 2", "Q&A")
MEASUREMENT_RECORDS = ("Real devices", "Room network", "Cost")
CANONICAL_ACT1_PROMPTS = (
    "teach me some salsa dance moves",
    "how do I throw a hot dog party",
    "recommend karaoke songs for a wedding",
)


def _section(text: str, heading: str) -> str:
    """Return the body of the `## heading` section, up to the next `## `."""
    match = re.search(
        rf"^## {re.escape(heading)}\b.*?$(.*?)(?=^## |\Z)",
        text,
        re.MULTILINE | re.DOTALL,
    )
    assert match, f"no '## {heading}' section"
    return match.group(1)


@pytest.mark.static
def test_carry_forward_doc_maps_every_portland_result() -> None:
    """Each proven result and each unmeasured gap from the debrief has a line."""
    assert CARRY_FORWARD.exists(), f"missing {CARRY_FORWARD}"
    text = CARRY_FORWARD.read_text(encoding="utf-8")
    proven = _section(text, "Proven at Portland")
    unmeasured = _section(text, "Still unmeasured")
    _section(text, "Hallway asks")
    missing = [i for i in PROVEN_ITEMS if i not in proven]
    missing += [i for i in UNMEASURED_ITEMS if i not in unmeasured]
    assert not missing, f"carry-forward doc does not cover: {missing}"


@pytest.mark.static
def test_cold_read_is_scheduled_clear_of_the_last_week() -> None:
    """The cold read has a date at least a week before the event opens."""
    text = CARRY_FORWARD.read_text(encoding="utf-8")
    cold_read = _section(text, "Cold read")
    dates = [
        dt.date.fromisoformat(d)
        for d in re.findall(r"\b(2026-\d{2}-\d{2})\b", cold_read)
    ]
    assert dates, "cold read section names no date"
    latest_allowed = EVENT_START - dt.timedelta(days=COLD_READ_MIN_LEAD_DAYS)
    assert min(dates) <= latest_allowed, (
        f"cold read {min(dates)} is later than {latest_allowed}; Portland "
        "only caught its unwinnable challenges by luck inside 72 hours"
    )


@pytest.mark.static
def test_runbook_provisions_the_night_before() -> None:
    """A night-before section precedes Pre-flight and runs the provisioning."""
    text = RUNBOOK.read_text(encoding="utf-8")
    night = text.find("## Night Before")
    preflight = text.find("## Pre-flight")
    assert night != -1, "RUNBOOK.md has no '## Night Before' section"
    assert night < preflight, "Night Before must come before Pre-flight"
    body = _section(text, "Night Before")
    assert "terraform apply" in body, "Night Before never provisions"


@pytest.mark.static
def test_runbook_act2_puts_existing_rule_files_on_screen() -> None:
    """Act 2 names the policy files that fired, and every one of them exists."""
    act2 = _section(RUNBOOK.read_text(encoding="utf-8"), "Act 2")
    paths = re.findall(r"`([\w./-]+\.(?:co|yaml))`", act2)
    assert paths, "Act 2 shows no rule file, only the toggle"
    missing = [p for p in paths if not (PROJECT_ROOT / p).is_file()]
    assert not missing, f"Act 2 names rule files that do not exist: {missing}"


@pytest.mark.static
def test_runbook_act1_uses_canonical_audience_prompts() -> None:
    """Act 1 hands the audience the lighthearted prompts, not attacks."""
    act1 = " ".join(_section(RUNBOOK.read_text(encoding="utf-8"), "Act 1").split()).lower()
    missing = [p for p in CANONICAL_ACT1_PROMPTS if p.lower() not in act1]
    assert not missing, f"Act 1 omits canonical prompts: {missing}"
    assert "jailbreak burritbot" not in act1, (
        "Act 1 invites the audience to attack; harder cases are presenter-driven"
    )


@pytest.mark.static
def test_runbook_has_a_measurements_record() -> None:
    """Timing per segment plus devices, network and cost each have a row."""
    body = _section(RUNBOOK.read_text(encoding="utf-8"), "Measurements")
    rows = [ln for ln in body.splitlines() if ln.startswith("|")]
    missing = [
        name
        for name in SEGMENTS + MEASUREMENT_RECORDS
        if not any(ln.startswith(f"| {name} ") for ln in rows)
    ]
    assert not missing, f"Measurements record has no row for: {missing}"
