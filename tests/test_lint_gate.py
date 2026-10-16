# ABOUTME: Static checks that the light Test command lints before it tests (issues #44, #62).
# ABOUTME: ruff is pinned in the dev group with an explicit rule set, and AGENTS.md runs it.

from __future__ import annotations

import re
import tomllib

import pytest

from conftest import PROJECT_ROOT


PYPROJECT = PROJECT_ROOT / "pyproject.toml"
AGENTS = PROJECT_ROOT / "AGENTS.md"
LINT = "uv run --managed-python --frozen ruff check ."
STATIC = "uv run --managed-python --frozen pytest -m static"


@pytest.mark.static
def test_ruff_is_pinned_in_the_dev_group() -> None:
    """ruff is an exact pin, so the gate does not move with a new release."""
    dev = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))["dependency-groups"]["dev"]
    pins = [dep for dep in dev if re.match(r"ruff\b", dep)]
    assert pins, "ruff is not in [dependency-groups].dev"
    assert re.fullmatch(r"ruff==\d+\.\d+\.\d+", pins[0]), f"ruff is not pinned exactly: {pins[0]!r}"


@pytest.mark.static
def test_ruff_rule_set_is_explicit() -> None:
    """An explicit select keeps a ruff upgrade from widening the gate on its own."""
    lint = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))["tool"]["ruff"]["lint"]
    assert lint.get("select"), "[tool.ruff.lint] has no explicit select"


@pytest.mark.static
def test_ruff_rejects_blind_and_silent_excepts() -> None:
    """The gate catches the silent fallbacks the 'no fallbacks' rule forbids (issue #62)."""
    select = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))["tool"]["ruff"]["lint"]["select"]
    missing = [code for code in ("BLE", "S110", "S112", "PLW1510") if code not in select]
    assert not missing, f"[tool.ruff.lint].select is missing {missing}"


@pytest.mark.static
def test_test_command_lints_then_tests() -> None:
    """The light Test command runs ruff before the static suite."""
    text = AGENTS.read_text(encoding="utf-8")
    match = re.search(r"^Test command: `(.+)`$", text, re.MULTILINE)
    assert match, "AGENTS.md has no 'Test command:' line"
    assert match.group(1) == f"{LINT} && {STATIC}", f"Test command is {match.group(1)!r}"
