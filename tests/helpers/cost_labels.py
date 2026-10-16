# ABOUTME: The delivery cost labels as Terraform defines them (labels.tf), and a delivery's slug from its runbook.
# ABOUTME: Shared by the Vertex AI request label tests (#82) so every call site is held to one definition.

from __future__ import annotations

import re
from pathlib import Path

from conftest import PROJECT_ROOT, TERRAFORM_DIR


LABELS_TF = TERRAFORM_DIR / "labels.tf"
PRESENTATIONS = PROJECT_ROOT / "presentations"
DELIVERY_LABEL = "burritbot-io_delivery"


def terraform_cost_labels(slug: str) -> dict[str, str]:
    """local.cost_labels from labels.tf, with var.delivery standing for slug."""
    body = re.search(r"cost_labels\s*=\s*\{(.*?)\}", LABELS_TF.read_text(encoding="utf-8"), re.S)
    assert body, "labels.tf has no local.cost_labels"
    pairs = re.findall(r'"([^"]+)"\s*=\s*("[^"]*"|var\.delivery)', body.group(1))
    assert pairs, "local.cost_labels is empty"
    return {k: slug if v == "var.delivery" else v.strip('"') for k, v in pairs}


def runbook_slug(event: str) -> str:
    """The slug the event's runbook applies Terraform with (`-var delivery=<slug>`)."""
    runbook = PRESENTATIONS / event / "docs" / "RUNBOOK.md"
    slugs = set(re.findall(r"-var\s+delivery=([\w-]+)", runbook.read_text(encoding="utf-8")))
    assert len(slugs) == 1, f"{runbook} names {sorted(slugs)} as the delivery slug, expected exactly one"
    return slugs.pop()


def event_of(path: Path) -> str:
    """The <event> of a path under presentations/<event>/."""
    rel = path.resolve().relative_to(PRESENTATIONS.resolve())
    return rel.parts[0]
