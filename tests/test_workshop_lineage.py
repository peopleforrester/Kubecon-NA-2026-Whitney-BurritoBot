# ABOUTME: Static check that the README says the workshop BurritoBot is not this platform's ancestor.
# ABOUTME: Keeps the independence recorded for issues #25 and #37 visible to readers of the README.

from __future__ import annotations

import re

import pytest

from conftest import PROJECT_ROOT


README = PROJECT_ROOT / "README.md"
WORKSHOP_REPO = "Unleash_an_Agent_Watch_It_Burn"


@pytest.mark.static
def test_readme_ancestry_disclaims_the_workshop_bot() -> None:
    """The README's Ancestry section names the workshop repo as a separate project, not a parent."""
    text = README.read_text(encoding="utf-8")
    match = re.search(r"^## Ancestry\b(.*?)(?=^## |\Z)", text, re.MULTILINE | re.DOTALL)
    assert match, "README.md has no '## Ancestry' section"
    section = match.group(1)
    assert WORKSHOP_REPO in section, f"README Ancestry does not name {WORKSHOP_REPO}"
    assert re.search(r"\bnot\b[^.]*\b(ancestor|fork|parent)\b", section), (
        f"README Ancestry names {WORKSHOP_REPO} without saying it is not an ancestor"
    )
