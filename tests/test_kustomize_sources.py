# ABOUTME: Kustomize source contract (#76) — Applications on a kustomization path build it with kustomize,
# ABOUTME: and every synced kustomization loads only files under its own root; mutation tests prove each bites.

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from conftest import PROJECT_ROOT
from helpers.manifest_graph import (
    directory_typed_kustomizations,
    files_outside_kustomization_root,
    kustomized_paths,
    load_manifests,
    load_restrictor_relaxed,
)


MANIFESTS = load_manifests(PROJECT_ROOT)
ARGOCD_VALUES = PROJECT_ROOT / "gitops" / "argocd" / "values.yaml"

# The wrapper Applications and the deploy/<x> path each one builds.
WRAPPERS = {
    "monitoring": "deploy/monitoring",
    "security": "deploy/security",
    "ai-gateway": "deploy/ai-gateway",
    "burritbot": "deploy/burritbot",
    "audience": "deploy/audience",
}


def _build_options() -> str:
    values = yaml.safe_load(ARGOCD_VALUES.read_text(encoding="utf-8"))
    return values["configs"]["cm"]["kustomize.buildOptions"]


def _app(name: str, path: str, directory: bool) -> dict:
    source: dict = {"repoURL": "https://example.invalid/repo.git", "path": path}
    if directory:
        source["directory"] = {"recurse": True}
    return {
        "apiVersion": "argoproj.io/v1alpha1",
        "kind": "Application",
        "metadata": {"name": name, "namespace": "argocd"},
        "spec": {"source": source},
    }


def _tree(root: Path, files: dict[str, object]) -> list:
    """Write files (dicts as YAML) under root and return the manifests found there."""
    for rel, content in files.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        text = content if isinstance(content, str) else yaml.safe_dump(content)
        (root / rel).write_text(text, encoding="utf-8")
    return load_manifests(root)


def _kustomization(*resources: str) -> dict:
    return {"apiVersion": "kustomize.config.k8s.io/v1beta1", "kind": "Kustomization", "resources": list(resources)}


CONFIGMAP = {"apiVersion": "v1", "kind": "ConfigMap", "metadata": {"name": "x", "namespace": "y"}}


# --- the repo ----------------------------------------------------------------


@pytest.mark.static
@pytest.mark.parametrize("name", sorted(WRAPPERS))
def test_wrapper_application_is_kustomize_sourced(name: str) -> None:
    """Each wrapper points at its deploy/<x> kustomization, so ArgoCD detects Kustomize."""
    apps = [m for m in MANIFESTS if m.kind == "Application" and m.name == name]
    assert len(apps) == 1, f"expected one Application {name}, found {[a.path for a in apps]}"
    path = apps[0].doc["spec"]["source"]["path"]
    assert path == WRAPPERS[name]
    assert (PROJECT_ROOT / path / "kustomization.yaml").is_file()


@pytest.mark.static
def test_no_application_forces_directory_on_a_kustomization() -> None:
    assert directory_typed_kustomizations(PROJECT_ROOT, MANIFESTS) == {}


@pytest.mark.static
def test_synced_kustomizations_load_only_files_under_their_root() -> None:
    options = _build_options()
    outside = files_outside_kustomization_root(PROJECT_ROOT, MANIFESTS)
    assert load_restrictor_relaxed(options) or outside == {}, (
        f"kustomize.buildOptions {options!r} keeps LoadRestrictionsRootOnly, so these builds fail:\n"
        + "\n".join(outside.values())
    )


@pytest.mark.static
@pytest.mark.parametrize("name", sorted(WRAPPERS))
def test_wrapper_renders_manifests(name: str) -> None:
    """Each wrapper renders at least one cluster object, not only the Kustomization."""
    app = next(m for m in MANIFESTS if m.kind == "Application" and m.name == name)
    rendered = kustomized_paths(PROJECT_ROOT, [app])
    kinds = {m.kind for m in MANIFESTS if m.path in rendered}
    assert kinds and "Kustomization" not in kinds, f"{name} renders {sorted(rendered)}"


# --- mutation tests ----------------------------------------------------------


@pytest.mark.static
@pytest.mark.parametrize("filename", ["kustomization.yaml", "kustomization.yml", "Kustomization"])
def test_mutation_directory_source_on_kustomization_is_caught(tmp_path: Path, filename: str) -> None:
    manifests = _tree(tmp_path, {
        "deploy/x/" + filename: _kustomization("cm.yaml"),
        "deploy/x/cm.yaml": CONFIGMAP,
        "gitops/apps/x.yaml": _app("x", "deploy/x", directory=True),
    })
    assert directory_typed_kustomizations(tmp_path, manifests).keys() == {"Application x"}


@pytest.mark.static
def test_directory_source_on_plain_manifests_is_allowed(tmp_path: Path) -> None:
    """Positive control: cert-manager-issuers' shape, plain YAML under a directory source."""
    manifests = _tree(tmp_path, {
        "security/cm/cm.yaml": CONFIGMAP,
        "gitops/apps/x.yaml": _app("x", "security/cm", directory=True),
    })
    assert directory_typed_kustomizations(tmp_path, manifests) == {}


@pytest.mark.static
def test_mutation_file_outside_root_is_caught(tmp_path: Path) -> None:
    """The #76 shape: a deploy wrapper listing a file from another tree."""
    manifests = _tree(tmp_path, {
        "deploy/x/kustomization.yaml": _kustomization("../../apps/x/cm.yaml"),
        "apps/x/cm.yaml": CONFIGMAP,
        "gitops/apps/x.yaml": _app("x", "deploy/x", directory=False),
    })
    assert files_outside_kustomization_root(tmp_path, manifests).keys() == {
        "deploy/x/kustomization.yaml: ../../apps/x/cm.yaml"
    }


@pytest.mark.static
def test_mutation_nested_file_outside_root_is_caught(tmp_path: Path) -> None:
    """A referenced directory's own kustomization is held to its own root too."""
    manifests = _tree(tmp_path, {
        "deploy/x/kustomization.yaml": _kustomization("../../apps/x"),
        "apps/x/kustomization.yaml": _kustomization("../shared/cm.yaml"),
        "apps/shared/cm.yaml": CONFIGMAP,
        "gitops/apps/x.yaml": _app("x", "deploy/x", directory=False),
    })
    assert files_outside_kustomization_root(tmp_path, manifests).keys() == {
        "apps/x/kustomization.yaml: ../shared/cm.yaml"
    }


@pytest.mark.static
def test_directory_resource_outside_root_is_allowed(tmp_path: Path) -> None:
    """Positive control: the shape the wrappers use, a directory with its own kustomization."""
    manifests = _tree(tmp_path, {
        "deploy/x/kustomization.yaml": _kustomization("../../apps/x"),
        "apps/x/kustomization.yaml": _kustomization("cm.yaml"),
        "apps/x/cm.yaml": CONFIGMAP,
        "gitops/apps/x.yaml": _app("x", "deploy/x", directory=False),
    })
    assert files_outside_kustomization_root(tmp_path, manifests) == {}
    assert kustomized_paths(tmp_path, manifests) == {"apps/x/cm.yaml"}


@pytest.mark.static
@pytest.mark.parametrize(("options", "relaxed"), [
    ("--enable-helm", False),
    ("--enable-helm --load-restrictor LoadRestrictionsNone", True),
    ("--load-restrictor=LoadRestrictionsNone", True),
    ("--load-restrictor LoadRestrictionsRootOnly", False),
])
def test_load_restrictor_parsing(options: str, relaxed: bool) -> None:
    assert load_restrictor_relaxed(options) is relaxed
