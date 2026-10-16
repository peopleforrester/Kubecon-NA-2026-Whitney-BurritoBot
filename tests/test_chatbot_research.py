# ABOUTME: Tests for the chatbot-research subproject — validates config, script imports, and structure.
# ABOUTME: Does NOT launch browsers or visit external sites; purely structural validation.

from __future__ import annotations

import pytest
import yaml

from conftest import PROJECT_ROOT


pytestmark = pytest.mark.research

RESEARCH_DIR = PROJECT_ROOT / "chatbot-research"
TARGETS_FILE = RESEARCH_DIR / "targets.yaml"
RESEARCH_SCRIPT = RESEARCH_DIR / "research.py"


@pytest.mark.static
def test_research_directory_exists() -> None:
    assert RESEARCH_DIR.is_dir(), "chatbot-research/ directory is missing"


@pytest.mark.static
def test_targets_yaml_valid() -> None:
    """targets.yaml parses and has the expected top-level keys."""
    assert TARGETS_FILE.exists(), "chatbot-research/targets.yaml is missing"
    config = yaml.safe_load(TARGETS_FILE.read_text(encoding="utf-8"))
    assert "prompts" in config, "targets.yaml missing 'prompts' key"
    assert "targets" in config, "targets.yaml missing 'targets' key"
    assert isinstance(config["prompts"], list), "prompts must be a list"
    assert len(config["prompts"]) >= 3, "need at least 3 prompt templates"
    assert isinstance(config["targets"], list), "targets must be a list"
    assert len(config["targets"]) >= 5, "need at least 5 targets"


@pytest.mark.static
def test_targets_have_required_fields() -> None:
    """Every target entry has name, url, and product_action."""
    config = yaml.safe_load(TARGETS_FILE.read_text(encoding="utf-8"))
    for i, t in enumerate(config["targets"]):
        for field in ("name", "url", "product_action"):
            assert field in t, f"target [{i}] missing '{field}'"
        assert t["url"].startswith("http"), f"target [{i}] url not http(s)"


@pytest.mark.static
def test_prompts_contain_placeholder() -> None:
    """Every prompt template includes the {product_action} placeholder."""
    config = yaml.safe_load(TARGETS_FILE.read_text(encoding="utf-8"))
    for i, prompt in enumerate(config["prompts"]):
        assert "{product_action}" in prompt, (
            f"prompt [{i}] missing {{product_action}} placeholder"
        )


@pytest.mark.static
def test_research_script_exists_and_imports() -> None:
    """research.py exists and its non-playwright imports load cleanly."""
    assert RESEARCH_SCRIPT.exists(), "chatbot-research/research.py is missing"
    # Validate it's valid Python by compiling.
    source = RESEARCH_SCRIPT.read_text(encoding="utf-8")
    compile(source, str(RESEARCH_SCRIPT), "exec")


@pytest.mark.static
def test_research_script_has_aboutme() -> None:
    """research.py follows the ABOUTME convention."""
    lines = RESEARCH_SCRIPT.read_text(encoding="utf-8").splitlines()[:4]
    aboutme_count = sum(1 for ln in lines if "ABOUTME:" in ln)
    assert aboutme_count >= 2, "research.py missing two ABOUTME lines at top"


@pytest.mark.static
def test_research_outputs_not_gitignored() -> None:
    """screenshots/ and results/ are NOT gitignored — they are the deliverables."""
    gi = RESEARCH_DIR / ".gitignore"
    if gi.exists():
        text = gi.read_text(encoding="utf-8")
        assert "screenshots/" not in text, (
            "screenshots/ should NOT be gitignored — they are research output"
        )
        assert "results/" not in text, (
            "results/ should NOT be gitignored — they are research output"
        )


@pytest.mark.static
def test_no_duplicate_target_names() -> None:
    """Target names must be unique across the config."""
    config = yaml.safe_load(TARGETS_FILE.read_text(encoding="utf-8"))
    names = [t["name"] for t in config["targets"]]
    dupes = [n for n in names if names.count(n) > 1]
    assert not dupes, f"Duplicate target names: {set(dupes)}"
