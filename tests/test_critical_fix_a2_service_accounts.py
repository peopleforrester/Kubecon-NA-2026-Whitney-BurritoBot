# ABOUTME: Phase A2 test — every serviceAccountName referenced in a Deployment must
# ABOUTME: have a matching ServiceAccount manifest; the guarded SA has no WIF annotation.

from __future__ import annotations

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
