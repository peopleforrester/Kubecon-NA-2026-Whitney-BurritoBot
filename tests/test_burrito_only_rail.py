# ABOUTME: The burrito-only rail must not list as off-topic what its own refusal offers (#102).
# ABOUTME: The rails ConfigMap the cluster mounts must carry each .co file unchanged.

from __future__ import annotations

import pytest
import yaml
from nemoguardrails.colang import parse_colang_file

from conftest import PROJECT_ROOT


NEMO_DIR = PROJECT_ROOT / "ai-gateway" / "nemo-guardrails"
RAILS_DIR = NEMO_DIR / "rails"
BURRITO_ONLY = RAILS_DIR / "burrito-only.co"
CONFIGMAP_RAILS = NEMO_DIR / "configmap-rails.yaml"

# What the refusal and config.yaml's instructions say BurritBot helps with.
OFFERED_SUBJECTS = ("menu", "hours", "location")


def _burrito_only() -> dict:
    return parse_colang_file(BURRITO_ONLY.name, BURRITO_ONLY.read_text(), version="1.0")


@pytest.mark.static
def test_refusal_names_every_offered_subject() -> None:
    (refusal,) = _burrito_only()["bot_messages"]["refuse off topic"]
    missing = [s for s in OFFERED_SUBJECTS if s not in refusal.lower()]
    assert not missing, f"the off-topic refusal no longer offers {missing}: {refusal!r}"


@pytest.mark.static
def test_no_off_topic_example_asks_about_an_offered_subject() -> None:
    """Refusing "what are your hours" with "I can help with hours" contradicts itself."""
    examples = _burrito_only()["user_messages"]["ask off topic"]
    contradictions = [e for e in examples if any(s in e.lower() for s in OFFERED_SUBJECTS)]
    assert not contradictions, (
        f"burrito-only.co lists {contradictions} as off-topic, but its refusal says "
        f"BurritBot helps with {', '.join(OFFERED_SUBJECTS)}"
    )


@pytest.mark.static
def test_hours_is_an_on_topic_example() -> None:
    assert "what are your hours" in _burrito_only()["user_messages"]["ask on topic"]


@pytest.mark.static
@pytest.mark.parametrize("rail", sorted(RAILS_DIR.glob("*.co")), ids=lambda p: p.name)
def test_rails_configmap_mirrors_the_rail_file(rail) -> None:
    configmap = yaml.safe_load(CONFIGMAP_RAILS.read_text())
    assert configmap["data"].get(rail.name) == rail.read_text(), (
        f"{CONFIGMAP_RAILS.name} carries a different {rail.name} than rails/{rail.name}; "
        f"the cluster mounts the ConfigMap, so copy the file into it"
    )
