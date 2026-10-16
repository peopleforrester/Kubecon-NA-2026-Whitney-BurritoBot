# ABOUTME: Static checks that a delivery can be costed by label from the Cloud Billing export.
# ABOUTME: Covers GKE resource labels, cost allocation, the export playbook, and the cost envelope.

from __future__ import annotations

import re

import pytest

from conftest import PROJECT_ROOT


TF_DIR = PROJECT_ROOT / "infrastructure" / "terraform"
GKE_TF = TF_DIR / "gke.tf"
LABELS_TF = TF_DIR / "labels.tf"
VARIABLES_TF = TF_DIR / "variables.tf"
SECRET_TF = TF_DIR / "secret-manager.tf"
TFVARS_EXAMPLE = TF_DIR / "terraform.tfvars.example"
BILLING_DOC = PROJECT_ROOT / "docs" / "BILLING-EXPORT.md"
TALK_DOCS = PROJECT_ROOT / "presentations" / "kubecon-na-2026" / "docs"
PLAN = TALK_DOCS / "PLAN.md"
BUILD = TALK_DOCS / "BUILD-INSTRUCTIONS.md"
RUNBOOK = TALK_DOCS / "RUNBOOK.md"

DELIVERY_LABEL = "burritbot-io_delivery"
# GCP label values: lowercase letters, digits, `_` and `-`, at most 63 chars.
LABEL_VALUE = re.compile(r"^[a-z0-9_-]{1,63}$")


def _uncommented(text: str) -> str:
    return "\n".join(line.split("#", 1)[0] for line in text.splitlines())


def _block(text: str, opener: str) -> str:
    """Return the brace-balanced body that follows `opener`."""
    start = re.search(opener, text)
    assert start, f"no block matching {opener!r}"
    depth = 0
    for i in range(start.end() - 1, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return text[start.end() : i]
    raise AssertionError(f"unbalanced block after {opener!r}")


def _section(text: str, heading: str) -> str:
    match = re.search(
        rf"^#+ {re.escape(heading)}.*?$(.*?)(?=^#+ |\Z)",
        text,
        re.MULTILINE | re.DOTALL,
    )
    assert match, f"no '{heading}' section"
    return match.group(1)


@pytest.mark.static
def test_delivery_variable_is_required_and_validated() -> None:
    """No default: an apply without a delivery fails instead of labelling wrong."""
    text = _uncommented(VARIABLES_TF.read_text())
    body = _block(text, r'variable\s+"delivery"\s*{')
    assert not re.search(r"^\s*default\s*=", body, re.MULTILINE), (
        "var.delivery must have no default; each delivery names itself"
    )
    assert "validation" in body, "var.delivery must validate as a GCP label value"


@pytest.mark.static
def test_cost_labels_carry_the_delivery() -> None:
    text = _uncommented(LABELS_TF.read_text())
    body = _block(text, r"cost_labels\s*=\s*{")
    assert re.search(rf'"{DELIVERY_LABEL}"\s*=\s*var\.delivery', body), (
        f"local.cost_labels must set {DELIVERY_LABEL} from var.delivery"
    )
    assert re.search(r'"burritbot-io_owner"\s*=\s*"burritbot"', body)


@pytest.mark.static
def test_gke_cluster_carries_cost_labels() -> None:
    """Cluster labels propagate to the node VMs and disks NAP creates."""
    text = _uncommented(GKE_TF.read_text())
    assert re.search(r"resource_labels\s*=\s*merge\(\s*local\.cost_labels", text), (
        "google_container_cluster must set resource_labels from local.cost_labels"
    )


@pytest.mark.static
def test_gke_cost_allocation_enabled() -> None:
    """Cost allocation puts namespace labels in the export: guarded vs unguarded."""
    text = _uncommented(GKE_TF.read_text())
    body = _block(text, r"cost_management_config\s*{")
    assert re.search(r"enabled\s*=\s*true", body)


@pytest.mark.static
def test_secret_carries_cost_labels() -> None:
    text = _uncommented(SECRET_TF.read_text())
    assert re.search(r"labels\s*=\s*merge\(\s*local\.cost_labels", text)


@pytest.mark.static
def test_tfvars_example_names_the_delivery_variable() -> None:
    text = _uncommented(TFVARS_EXAMPLE.read_text())
    assert re.search(r"^\s*delivery\s*=", text, re.MULTILINE)


@pytest.mark.static
def test_billing_export_playbook_keeps_the_dataset_out_of_teardown() -> None:
    """The export dataset outlives `terraform destroy`; billing data lands hours later."""
    assert BILLING_DOC.is_file(), f"missing {BILLING_DOC}"
    text = BILLING_DOC.read_text(encoding="utf-8")
    assert "bq mk" in text, "playbook must create the export dataset"
    assert DELIVERY_LABEL in text, "playbook query must filter on the delivery label"
    assert "teardown" in text.lower()
    tf = "\n".join(p.read_text() for p in TF_DIR.glob("*.tf"))
    assert "google_bigquery_dataset" not in _uncommented(tf), (
        "the export dataset must not live in the module teardown.sh destroys"
    )


@pytest.mark.static
def test_runbook_applies_with_a_delivery_label_and_reads_cost_from_export() -> None:
    text = RUNBOOK.read_text(encoding="utf-8")
    night = _section(text, "Night Before")
    match = re.search(r"-var\s+delivery=([\w-]+)", night)
    assert match, "Night Before apply must pass -var delivery=<slug>"
    assert LABEL_VALUE.match(match.group(1)), f"{match.group(1)} is not a label value"
    assert "docs/BILLING-EXPORT.md" in text, "the Cost row must point at the playbook"


@pytest.mark.static
def test_cost_envelopes_price_the_pinned_model() -> None:
    """Gemini 2.5 Flash retired 2026-10-16; the envelope prices gemini-3-pro."""
    for path, heading in ((PLAN, "9. Cost Envelope"), (BUILD, "Cost Estimate")):
        body = _section(path.read_text(encoding="utf-8"), heading)
        assert not re.search(r"Flash", body), f"{path.name} still prices a Flash model"
        assert "Gemini 3 Pro" in body, f"{path.name} does not price Gemini 3 Pro"
