# ABOUTME: Phase A6 test — PROJECT_STATE.md's stated static-test total must equal reality.
# ABOUTME: Drift here violates the state-persistence rule ("never green-wash the scorecard").

from __future__ import annotations

import re
import subprocess
import sys

import pytest

from conftest import PROJECT_ROOT


PROJECT_STATE = PROJECT_ROOT / "PROJECT_STATE.md"
TOTAL_PATTERN = re.compile(r"Total:\s*(\d+)\s*static\s*tests")


def _collected_static_count() -> int:
    """Run pytest --collect-only -m static and parse the count."""
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", "-m", "static"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    match = re.search(r"(\d+)\s*/\s*\d+\s*tests collected", result.stdout)
    if match:
        return int(match.group(1))
    match = re.search(r"(\d+)\s*tests collected", result.stdout)
    assert match, f"could not parse pytest collect output:\n{result.stdout}"
    return int(match.group(1))


@pytest.mark.static
def test_project_state_static_test_count_is_current() -> None:
    """The number stated in PROJECT_STATE.md must match what pytest collects today."""
    text = PROJECT_STATE.read_text()
    match = TOTAL_PATTERN.search(text)
    assert match, "PROJECT_STATE.md has no 'Total: N static tests' line"
    stated = int(match.group(1))
    actual = _collected_static_count()
    assert stated == actual, (
        f"PROJECT_STATE.md says {stated} static tests; pytest collects "
        f"{actual}. Refresh the state file — see "
        f"~/.claude/rules/state-persistence.md (no green-washing)."
    )


@pytest.mark.static
def test_project_state_has_one_branch_and_tests_section() -> None:
    """One branch/test status section, and its count agrees with the Total line (#46)."""
    text = PROJECT_STATE.read_text()
    headings = re.findall(r"^## Branch & Tests?\b.*$", text, re.MULTILINE)
    assert len(headings) == 1, (
        f"PROJECT_STATE.md has {len(headings)} branch/test status sections "
        f"({headings}); keep only the lifecycle header's '## Branch & Tests'."
    )
    section = text.split(headings[0], 1)[1].split("\n## ", 1)[0]
    passed = re.search(r"(\d+)\s+passed", section)
    assert passed, "'## Branch & Tests' does not state an 'N passed' count"
    total = TOTAL_PATTERN.search(text)
    assert total, "PROJECT_STATE.md has no 'Total: N static tests' line"
    assert passed.group(1) == total.group(1), (
        f"'## Branch & Tests' says {passed.group(1)} passed; the Total line "
        f"says {total.group(1)}."
    )
