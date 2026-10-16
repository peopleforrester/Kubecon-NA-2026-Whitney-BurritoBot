# ABOUTME: Static checks for the fleet talk-repo standard: README identity, AGENTS.md pointers, state files.
# ABOUTME: README and AGENTS.md name talks-knowledge for the register and abstracts (issue #40).

from __future__ import annotations

import re

import pytest

from conftest import PROJECT_ROOT


README = PROJECT_ROOT / "README.md"
AGENTS = PROJECT_ROOT / "AGENTS.md"
CLAUDE = PROJECT_ROOT / "CLAUDE.md"
TALKS = "peopleforrester/talks-knowledge"
CONFERENCES = "peopleforrester/conference-knowledge"


def _section(text: str, heading: str) -> str:
    match = re.search(rf"^## {heading}\b(.*?)(?=^## |\Z)", text, re.MULTILINE | re.DOTALL)
    assert match, f"no '## {heading}' section"
    return re.sub(r"\s+", " ", match.group(1))


@pytest.mark.static
def test_readme_states_who_this_repo_is() -> None:
    """README's 'The Talk' section names title, speakers, argument, event, status and sources."""
    section = _section(README.read_text(encoding="utf-8"), "The Talk")
    for needed in (
        "BurritoBot Said Let's Dance, the Platform Said No",
        "Whitney Lee",
        "Michael Forrester",
        "platform-level governance",
        "Salt Lake City",
        "kubeauto-ai-day",
        "spinybacked-orbweaver",
        "PROJECT_STATE.md",
    ):
        assert needed in section, f"README 'The Talk' section lacks {needed!r}"


@pytest.mark.static
def test_readme_status_names_the_europe_2027_slate() -> None:
    """The status says BurritoBot is on the EU 2027 slate, submitted by Whitney, and not built here."""
    section = _section(README.read_text(encoding="utf-8"), "The Talk")
    assert re.search(r"EU 2027[^.]*Whitney|Whitney[^.]*EU 2027", section), (
        "README status does not say BurritoBot is on the EU 2027 slate, submitted by Whitney"
    )
    assert "decisions.md" in section, "README status does not point at the #37 decision"


@pytest.mark.static
@pytest.mark.parametrize("path", [README, AGENTS], ids=["README.md", "AGENTS.md"])
def test_where_things_live_names_both_knowledge_repos(path) -> None:
    """'Where things live' names talks-knowledge for the register and abstracts, conference-knowledge for events."""
    section = _section(path.read_text(encoding="utf-8"), "Where things live")
    assert TALKS in section, f"{path.name} 'Where things live' does not name {TALKS}"
    assert "talks/register.md" in section, f"{path.name} does not point at the talk register"
    assert "abstract" in section, f"{path.name} does not say where the abstracts live"
    assert CONFERENCES in section, f"{path.name} 'Where things live' does not name {CONFERENCES}"


@pytest.mark.static
def test_state_files_follow_the_fleet_standard() -> None:
    """CLAUDE.md is a symlink to AGENTS.md, and PROJECT_STATE.md and decisions.md exist."""
    assert CLAUDE.is_symlink(), "CLAUDE.md is not a symlink"
    assert CLAUDE.resolve() == AGENTS.resolve(), "CLAUDE.md does not point at AGENTS.md"
    assert (PROJECT_ROOT / "PROJECT_STATE.md").is_file(), "PROJECT_STATE.md is missing"
    decisions = PROJECT_ROOT / "decisions.md"
    assert decisions.is_file(), "decisions.md is missing"
    assert "Append-only" in decisions.read_text(encoding="utf-8"), "decisions.md does not say it is append-only"
