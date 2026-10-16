# ABOUTME: Phase A1 test — every ArgoCD Application path: must resolve to a real dir.
# ABOUTME: Caught only by behavior validation; static "yaml exists" tests would miss this.

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

from conftest import PROJECT_ROOT


GITOPS_APPS_DIR = PROJECT_ROOT / "gitops" / "apps"
PINNED_CHART_VERSION = re.compile(r"^v?\d+\.\d+\.\d+$")


def _load_applications() -> list[tuple[Path, dict]]:
    """Yield (file_path, manifest_dict) for every ArgoCD Application."""
    apps: list[tuple[Path, dict]] = []
    for yaml_file in sorted(GITOPS_APPS_DIR.glob("*.yaml")):
        with yaml_file.open() as fp:
            for doc in yaml.safe_load_all(fp):
                if not doc:
                    continue
                if doc.get("kind") == "Application":
                    apps.append((yaml_file, doc))
    return apps


def _app_id(x: Path | dict) -> str:
    return x.name if isinstance(x, Path) else x.get("metadata", {}).get("name", "?")


APPLICATIONS = _load_applications()
PATH_APPS = [(f, a) for f, a in APPLICATIONS if "chart" not in a["spec"]["source"]]
CHART_APPS = [(f, a) for f, a in APPLICATIONS if "chart" in a["spec"]["source"]]


@pytest.mark.static
def test_applications_load() -> None:
    """At least one ArgoCD Application loads, so the parametrized checks run."""
    assert APPLICATIONS, f"no ArgoCD Applications found under {GITOPS_APPS_DIR}"


@pytest.mark.static
@pytest.mark.parametrize("yaml_file,app", CHART_APPS, ids=_app_id)
def test_argocd_helm_application_pins_chart(yaml_file: Path, app: dict) -> None:
    """Every Helm-source Application names a chart repo and an exact chart version."""
    source = app["spec"]["source"]
    assert source.get("repoURL"), f"{yaml_file.name}: spec.source.repoURL is missing"
    revision = str(source.get("targetRevision", ""))
    assert PINNED_CHART_VERSION.match(revision), (
        f"{yaml_file.name}: chart {source['chart']!r} targetRevision {revision!r} "
        "is not an exact version"
    )


@pytest.mark.static
@pytest.mark.parametrize("yaml_file,app", PATH_APPS, ids=_app_id)
def test_argocd_application_path_resolves(yaml_file: Path, app: dict) -> None:
    """Every Git-source Application must point to an existing populated dir."""
    source = app["spec"]["source"]

    path = source.get("path")
    assert path, f"{yaml_file.name}: spec.source.path is missing"

    target = PROJECT_ROOT / path
    assert target.is_dir(), (
        f"{yaml_file.name}: path '{path}' does not exist at {target}"
    )

    yaml_files = list(target.rglob("*.yaml")) + list(target.rglob("*.yml"))
    assert yaml_files, (
        f"{yaml_file.name}: path '{path}' contains no yaml files"
    )
