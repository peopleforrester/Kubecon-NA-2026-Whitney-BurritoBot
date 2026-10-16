# ABOUTME: Static guard that no test skips, xfails or exits instead of failing (issue #61).
# ABOUTME: A live test with a missing cluster, tool or credential must fail loudly, not skip.

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from conftest import PROJECT_ROOT


TESTS_DIR = PROJECT_ROOT / "tests"

# Attribute names that turn a test into a skip, an expected failure or an
# early exit: pytest.skip / importorskip / xfail / exit, pytest.mark.skip /
# skipif / xfail, unittest.skip* and TestCase.skipTest.
BANNED_ATTRS = {
    "skip",
    "skipif",
    "importorskip",
    "xfail",
    "exit",
    "skipTest",
    "skipIf",
    "skipUnless",
    "expectedFailure",
}
BANNED_NAMES = {"KNOWN_OPEN"}


def _python_test_files() -> list[Path]:
    return sorted(TESTS_DIR.rglob("*.py"))


def _offences(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr in BANNED_ATTRS:
            base = node.value
            owner = base.attr if isinstance(base, ast.Attribute) else getattr(base, "id", "")
            if owner in {"pytest", "mark", "unittest", "self"}:
                found.append(f"{path.relative_to(PROJECT_ROOT)}:{node.lineno} {owner}.{node.attr}")
        elif isinstance(node, ast.Name) and node.id in BANNED_NAMES:
            found.append(f"{path.relative_to(PROJECT_ROOT)}:{node.lineno} {node.id}")
    return found


@pytest.mark.static
def test_no_test_skips_xfails_or_exits() -> None:
    """Missing prerequisites fail the test with a message; nothing skips."""
    offences = [o for path in _python_test_files() for o in _offences(path)]
    assert not offences, "skip paths in the test suite:\n" + "\n".join(offences)
