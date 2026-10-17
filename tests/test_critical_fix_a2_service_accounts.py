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
