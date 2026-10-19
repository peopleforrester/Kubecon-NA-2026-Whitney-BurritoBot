# ABOUTME: Phase A2 test — every serviceAccountName referenced in a Deployment must
# ABOUTME: have a matching SA manifest; the guarded SA has no WIF annotation, as PROJECT_STATE.md says.

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

from conftest import PROJECT_ROOT


APPS_DIR = PROJECT_ROOT / "apps"
WIF_ANNOTATION_KEY = "iam.gke.io/gcp-service-account"


def _load_yaml_docs(path: Path) -> list[dict]:
    with path.open() as fp:
        return [d for d in yaml.safe_load_all(fp) if d]


def _collect_deployment_sa_refs() -> list[tuple[Path, dict]]:
    """Return (path, deployment) for every Deployment with a serviceAccountName."""
    refs: list[tuple[Path, dict]] = []
    for yaml_file in APPS_DIR.rglob("k8s/*.yaml"):
        for doc in _load_yaml_docs(yaml_file):
            if doc.get("kind") != "Deployment":
                continue
            sa = doc.get("spec", {}).get("template", {}).get("spec", {}).get(
                "serviceAccountName"
            )
            if sa:
                refs.append((yaml_file, doc))
    return refs


def _find_sa_manifest(name: str, namespace: str) -> dict | None:
    """Walk apps/ looking for a ServiceAccount with matching name + namespace."""
    for yaml_file in APPS_DIR.rglob("*.yaml"):
        for doc in _load_yaml_docs(yaml_file):
            if doc.get("kind") != "ServiceAccount":
                continue
            md = doc.get("metadata", {})
            if md.get("name") == name and md.get("namespace") == namespace:
                return doc
    return None


@pytest.mark.static
@pytest.mark.parametrize(
    "deployment_path,deployment",
    _collect_deployment_sa_refs(),
    ids=lambda x: x.name if isinstance(x, Path) else x.get("metadata", {}).get("name", "?"),
)
def test_referenced_service_account_exists(
    deployment_path: Path, deployment: dict
) -> None:
    """Every serviceAccountName in a Deployment must have a matching SA manifest."""
    sa_name = deployment["spec"]["template"]["spec"]["serviceAccountName"]
    namespace = deployment["metadata"]["namespace"]

    sa = _find_sa_manifest(sa_name, namespace)
    assert sa is not None, (
        f"{deployment_path.name}: ServiceAccount '{sa_name}' in namespace "
        f"'{namespace}' is referenced but not defined anywhere under apps/"
    )


@pytest.mark.static
def test_burritbot_guarded_sa_has_no_wif_annotation() -> None:
    """Guarded BurritBot reaches Vertex only through the AI gateway (#67), so
    its SA must not impersonate a GSA (question 163)."""
    sa = _find_sa_manifest("burritbot", "burritbot-guarded")
    assert sa is not None, "burritbot SA in burritbot-guarded missing"

    annotations = sa.get("metadata", {}).get("annotations", {}) or {}
    assert WIF_ANNOTATION_KEY not in annotations, (
        f"burritbot SA in burritbot-guarded carries {WIF_ANNOTATION_KEY}="
        f"{annotations.get(WIF_ANNOTATION_KEY)!r}; only the gateway proxy's GSA "
        f"may reach Vertex"
    )


GUARDED_SA_PATH = APPS_DIR / "burritbot" / "k8s" / "serviceaccount-burritbot-guarded.yaml"

# The labels the guarded SA carried before #116 dropped its WIF annotation;
# that change left them alone, and Kyverno and the dashboards select on them.
GUARDED_SA_LABELS = {
    "app.kubernetes.io/name": "burritbot",
    "app.kubernetes.io/part-of": "burritbot",
    "burritbot.io/layer": "application",
    "burritbot.io/guarded": "true",
}


def _aboutme_lines(path: Path) -> list[str]:
    return [
        line
        for line in path.read_text().splitlines()
        if line.startswith("# ABOUTME:")
    ]


@pytest.mark.static
def test_burritbot_guarded_sa_aboutme_does_not_claim_wif_binding() -> None:
    """The guarded SA's ABOUTME lines must not say it is bound via WIF to the
    workload GSA, which it no longer is (#116, question 163)."""
    lines = _aboutme_lines(GUARDED_SA_PATH)
    assert len(lines) == 2, (
        f"{GUARDED_SA_PATH.name} must open with two ABOUTME lines, found {lines!r}"
    )
    for line in lines:
        lowered = line.lower()
        assert "bound via wif" not in lowered, (
            f"{GUARDED_SA_PATH.name} ABOUTME still claims a WIF binding: {line!r}"
        )
        assert "workload gsa" not in lowered, (
            f"{GUARDED_SA_PATH.name} ABOUTME still names the workload GSA: {line!r}"
        )
        assert "gsa email" not in lowered, (
            f"{GUARDED_SA_PATH.name} ABOUTME still mentions a GSA email "
            f"placeholder: {line!r}"
        )


@pytest.mark.static
def test_burritbot_guarded_sa_labels_and_token_automount_unchanged() -> None:
    """Dropping the WIF annotation (#116) left the guarded SA's labels and
    automountServiceAccountToken as they were."""
    docs = _load_yaml_docs(GUARDED_SA_PATH)
    assert len(docs) == 1, f"{GUARDED_SA_PATH.name} must hold one document"
    sa = docs[0]
    assert sa.get("kind") == "ServiceAccount"
    md = sa.get("metadata", {})
    assert (md.get("name"), md.get("namespace")) == ("burritbot", "burritbot-guarded")

    assert md.get("labels") == GUARDED_SA_LABELS, (
        f"{GUARDED_SA_PATH.name} labels changed: {md.get('labels')!r}"
    )
    assert sa.get("automountServiceAccountToken") is True, (
        f"{GUARDED_SA_PATH.name} automountServiceAccountToken must stay true, "
        f"found {sa.get('automountServiceAccountToken')!r}"
    )


PROJECT_STATE = PROJECT_ROOT / "PROJECT_STATE.md"

# The Phase History line #116 added for #95's first child.
PHASE_95_LINE = re.compile(r"^- \d{4}-\d{2}-\d{2}\S* · #95 .*\bfirst child #116\b.*$")
# The C2 row's claim before #116, which presented the annotation as current.
OLD_C2_FIX = "ServiceAccount manifests added; WIF annotation on guarded SA"


def _section(text: str, heading: str) -> str:
    """The body of a PROJECT_STATE.md '## ' section, up to the next rule or heading."""
    match = re.search(rf"^## {re.escape(heading)}\n(.*?)(?=^---$|^## )", text, re.M | re.S)
    assert match, f"PROJECT_STATE.md has no '## {heading}' section"
    return match.group(1)


def phase_history_95_violations(text: str) -> list[str]:
    """Why Phase History does not hold exactly one #95 line recording #116."""
    lines = [
        line
        for line in _section(text, "Phase History").splitlines()
        if PHASE_95_LINE.match(line)
    ]
    if len(lines) != 1:
        return [f"Phase History has {len(lines)} '#95 ... first child #116' lines, not one"]
    line = lines[0]
    return [
        f"the #95 Phase History line does not mention {needle!r}"
        for needle in (
            "question 163",
            "`burritbot-guarded/burritbot`",
            f"`{WIF_ANNOTATION_KEY}`",
            "test_burritbot_guarded_sa_has_no_wif_annotation",
        )
        if needle not in line
    ]


def c2_row_violations(text: str) -> list[str]:
    """Why the Critical Fixes C2 row does not say the guarded SA has no WIF annotation."""
    rows = [
        [cell.strip() for cell in line.strip().strip("|").split("|")]
        for line in _section(text, "Critical Fixes (2026-04-25 senior review)").splitlines()
        if line.startswith("|")
    ]
    c2 = [row for row in rows if row[0] == "C2"]
    if len(c2) != 1:
        return [f"Critical Fixes has {len(c2)} C2 rows, not one"]
    fix, test = c2[0][1], c2[0][2]
    problems = []
    if "guarded SA has no WIF annotation (#95, question 163)" not in fix:
        problems.append(f"C2 row does not say the guarded SA has no WIF annotation: {fix!r}")
    if re.search(r"WIF annotation on (the )?guarded SA", fix, re.I):
        problems.append(f"C2 row presents the guarded SA's WIF annotation as current: {fix!r}")
    if test != "`test_critical_fix_a2_service_accounts.py`":
        problems.append(f"C2 row no longer names the A2 test file: {test!r}")
    return problems


@pytest.mark.static
def test_phase_history_has_one_line_for_95_first_child() -> None:
    """#116 added one Phase History line for #95 naming the dropped annotation."""
    assert phase_history_95_violations(PROJECT_STATE.read_text()) == []


@pytest.mark.static
def test_critical_fixes_c2_row_says_guarded_sa_has_no_wif_annotation() -> None:
    """The C2 row no longer presents the guarded SA's WIF annotation as current."""
    assert c2_row_violations(PROJECT_STATE.read_text()) == []


def _pre_116_state() -> str:
    """PROJECT_STATE.md as #116 found it: no #95 line, the old C2 claim."""
    text = PROJECT_STATE.read_text()
    text = "\n".join(line for line in text.splitlines() if not PHASE_95_LINE.match(line))
    return re.sub(r"(\| C2  \| )[^|]*", rf"\g<1>{OLD_C2_FIX}   ", text)


@pytest.mark.static
def test_pre_116_project_state_fails_both_checks() -> None:
    text = _pre_116_state()
    assert phase_history_95_violations(text) == [
        "Phase History has 0 '#95 ... first child #116' lines, not one"
    ]
    problems = c2_row_violations(text)
    assert any("does not say the guarded SA has no WIF annotation" in p for p in problems)
    assert any("as current" in p for p in problems)


@pytest.mark.static
def test_a_second_95_first_child_line_fails() -> None:
    text = PROJECT_STATE.read_text()
    line = next(
        line for line in _section(text, "Phase History").splitlines() if PHASE_95_LINE.match(line)
    )
    doubled = text.replace(line, f"{line}\n{line}", 1)
    assert phase_history_95_violations(doubled) == [
        "Phase History has 2 '#95 ... first child #116' lines, not one"
    ]


@pytest.mark.static
def test_c2_row_restating_the_annotation_as_current_fails() -> None:
    text = PROJECT_STATE.read_text().replace(
        "guarded SA has no WIF annotation (#95, question 163)",
        "guarded SA has no WIF annotation (#95, question 163); WIF annotation on guarded SA",
        1,
    )
    assert any("as current" in p for p in c2_row_violations(text))
