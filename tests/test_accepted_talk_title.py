# ABOUTME: Talk-title test — the retired working title must not appear anywhere in the repo.
# ABOUTME: The accepted talk title is "BurritoBot Said Let's Dance, the Platform Said No".

from __future__ import annotations

import re
from pathlib import Path

import pytest

from conftest import PROJECT_ROOT


ACCEPTED_TITLE = "BurritoBot Said Let's Dance, the Platform Said No"

# The retired working title, matched across line wraps and markdown
# emphasis. Assembled from parts so this file does not carry it verbatim.
RETIRED_TITLE_PATTERN = re.compile(
    r"Can\s+Your\s+Chatbot\s+Run\s+" + "kube" + r"ctl\s*\?", re.IGNORECASE
)

SKIP_DIRS = {
    ".git",
    ".venv",
    "__pycache__",
    ".pytest_cache",
    "node_modules",
    # Gitignored local-only archive of imported conversations; never public.
    "claude-ai-context",
}

EXTENSION_SKIP = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".pdf", ".lock"}

# Files that name the talk: each must carry the accepted title.
TITLE_BEARING_FILES = [
    "README.md",
    "presentations/kubecon-na-2026/docs/PLAN.md",
    "presentations/kubecon-na-2026/docs/CFP-SUBMISSION.md",
    "presentations/kubecon-na-2026/docs/BUILD-INSTRUCTIONS.md",
]


def _iter_text_files() -> list[Path]:
    files: list[Path] = []
    for p in PROJECT_ROOT.rglob("*"):
        if not p.is_file():
            continue
        if set(p.relative_to(PROJECT_ROOT).parts) & SKIP_DIRS:
            continue
        if p.suffix.lower() in EXTENSION_SKIP:
            continue
        files.append(p)
    return files


@pytest.mark.static
def test_no_file_carries_retired_talk_title() -> None:
    """The retired working title must not appear in any file."""
    offenders: list[str] = []
    for path in _iter_text_files():
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        if RETIRED_TITLE_PATTERN.search(text):
            offenders.append(str(path.relative_to(PROJECT_ROOT)))
    assert not offenders, (
        "Retired talk title found; replace it with the accepted title "
        f"{ACCEPTED_TITLE!r} in: {sorted(offenders)}"
    )


@pytest.mark.static
@pytest.mark.parametrize("rel", TITLE_BEARING_FILES)
def test_title_bearing_files_carry_accepted_title(rel: str) -> None:
    """Each file that names the talk names it by its accepted title."""
    text = (PROJECT_ROOT / rel).read_text(encoding="utf-8")
    flattened = re.sub(r"\s+", " ", text)
    assert ACCEPTED_TITLE in flattened, f"{rel} does not carry {ACCEPTED_TITLE!r}"
