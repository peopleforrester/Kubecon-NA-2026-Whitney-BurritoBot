# ABOUTME: Synced-manifest contract (#106) — every cluster manifest in the repo is applied by some ArgoCD
# ABOUTME: Application, Kustomize or Directory source; tmp-tree cases pin recurse, include, exclude and detection.

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from conftest import PROJECT_ROOT
from helpers.manifest_graph import (
    directory_files,
    glob_match,
    kustomized_paths,
    load_manifests,
    source_type,
    synced_paths,
    unsynced_manifests,
)


MANIFESTS = load_manifests(PROJECT_ROOT)

# Applied once by hand (`kubectl apply -f`), the one exception to "no kubectl
# apply" (AGENTS.md Rules); after that the root Application syncs gitops/apps.
BOOTSTRAP = {"gitops/bootstrap/app-of-apps.yaml"}

# Directory-source Applications in the repo and a file each one applies.
# kustomized_paths alone counted none of these.
DIRECTORY_SOURCES = {
    "root": "gitops/apps/cert-manager-issuers.yaml",
    "cert-manager-issuers": "security/cert-manager/cluster-issuers.yaml",
    "namespaces": "gitops/namespaces/namespaces.yaml",
}

CONFIGMAP = {"apiVersion": "v1", "kind": "ConfigMap", "metadata": {"name": "x", "namespace": "y"}}


def _app(name: str, path: str | None = None, **source: object) -> dict:
    src: dict = {"repoURL": "https://example.invalid/repo.git", **source}
    if path is not None:
        src["path"] = path
    return {
        "apiVersion": "argoproj.io/v1alpha1",
        "kind": "Application",
        "metadata": {"name": name, "namespace": "argocd"},
        "spec": {"source": src},
    }


def _tree(root: Path, files: dict[str, object]) -> list:
    """Write files (dicts as YAML) under root and return the manifests found there."""
    for rel, content in files.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        text = content if isinstance(content, str) else yaml.safe_dump(content)
        (root / rel).write_text(text, encoding="utf-8")
    return load_manifests(root)


def _application(name: str) -> list:
    return [m for m in MANIFESTS if m.kind == "Application" and m.name == name]


# --- the repo ----------------------------------------------------------------


@pytest.mark.static
def test_every_cluster_manifest_is_synced_by_an_application() -> None:
    synced = synced_paths(PROJECT_ROOT, MANIFESTS)
    unsynced = unsynced_manifests([m for m in MANIFESTS if m.path not in BOOTSTRAP], synced)
    assert unsynced == {}, "\n".join(unsynced.values())


@pytest.mark.static
def test_bootstrap_is_not_synced_and_syncs_gitops_apps() -> None:
    """The hand-applied root is the only exception, and it is what applies gitops/apps."""
    synced = synced_paths(PROJECT_ROOT, MANIFESTS)
    assert not BOOTSTRAP & synced
    (root,) = _application("root")
    assert root.path in BOOTSTRAP
    apps = {str(p.relative_to(PROJECT_ROOT)) for p in (PROJECT_ROOT / "gitops" / "apps").glob("*.yaml")}
    assert apps <= synced_paths(PROJECT_ROOT, [root])


@pytest.mark.static
@pytest.mark.parametrize(("name", "path"), sorted(DIRECTORY_SOURCES.items()))
def test_directory_source_application_is_counted(name: str, path: str) -> None:
    (app,) = _application(name)
    assert source_type(PROJECT_ROOT, app.doc["spec"]["source"]) == "Directory"
    assert path in synced_paths(PROJECT_ROOT, [app])
    assert path not in kustomized_paths(PROJECT_ROOT, MANIFESTS)


@pytest.mark.static
def test_mutation_dropped_directory_application_is_caught() -> None:
    """Without cert-manager-issuers nothing applies the ClusterIssuers."""
    without = [m for m in MANIFESTS if not (m.kind == "Application" and m.name == "cert-manager-issuers")]
    unsynced = unsynced_manifests([m for m in without if m.path not in BOOTSTRAP], synced_paths(PROJECT_ROOT, without))
    assert unsynced.keys() == {
        "security/cert-manager/cluster-issuers.yaml: ClusterIssuer None/letsencrypt-staging",
        "security/cert-manager/cluster-issuers.yaml: ClusterIssuer None/letsencrypt-production",
    }


@pytest.mark.static
def test_mutation_dropped_root_application_is_caught() -> None:
    without = [m for m in MANIFESTS if m.path not in BOOTSTRAP]
    unsynced = unsynced_manifests(without, synced_paths(PROJECT_ROOT, without))
    assert {key.split(": ")[0] for key in unsynced} == {
        str(p.relative_to(PROJECT_ROOT)) for p in (PROJECT_ROOT / "gitops" / "apps").glob("*.yaml")
    }


# --- directory sources (ArgoCD reposerver findManifests) ------------------------


@pytest.mark.static
def test_directory_without_recurse_reads_only_the_top_level(tmp_path: Path) -> None:
    manifests = _tree(tmp_path, {
        "apps/d/top.yaml": CONFIGMAP,
        "apps/d/sub/nested.yaml": CONFIGMAP,
        "gitops/apps/x.yaml": _app("x", "apps/d", directory={}),
    })
    assert synced_paths(tmp_path, manifests) == {"apps/d/top.yaml"}
    unsynced = unsynced_manifests(manifests, synced_paths(tmp_path, manifests))
    assert unsynced.keys() == {"apps/d/sub/nested.yaml: ConfigMap y/x", "gitops/apps/x.yaml: Application argocd/x"}


@pytest.mark.static
def test_directory_with_recurse_reads_subdirectories(tmp_path: Path) -> None:
    manifests = _tree(tmp_path, {
        "d/top.yaml": CONFIGMAP,
        "d/sub/deeper/nested.yml": CONFIGMAP,
        "gitops/apps/x.yaml": _app("x", "d", directory={"recurse": True}),
    })
    assert synced_paths(tmp_path, manifests) == {"d/top.yaml", "d/sub/deeper/nested.yml"}


@pytest.mark.static
def test_directory_reads_only_manifest_extensions(tmp_path: Path) -> None:
    _tree(tmp_path, {
        "d/a.yaml": CONFIGMAP, "d/b.yml": CONFIGMAP, "d/c.json": "{}",
        "d/d.jsonnet": "{}", "d/e.txt": "", "d/f.yaml.bak": "",
    })
    assert directory_files(tmp_path, "d", {}) == {"d/a.yaml", "d/b.yml", "d/c.json", "d/d.jsonnet"}
    assert directory_files(tmp_path, "d", {"disableExtensionFilter": True}) >= {"d/e.txt", "d/f.yaml.bak"}


@pytest.mark.static
def test_directory_include_matches_across_subdirectories(tmp_path: Path) -> None:
    """The root app's shape: include "*.yaml" with recurse. gobwas `*` crosses `/` (no separators)."""
    _tree(tmp_path, {"d/a.yaml": CONFIGMAP, "d/sub/b.yaml": CONFIGMAP, "d/c.yml": CONFIGMAP})
    assert directory_files(tmp_path, "d", {"recurse": True, "include": "*.yaml"}) == {"d/a.yaml", "d/sub/b.yaml"}


@pytest.mark.static
def test_directory_exclude_wins_over_include(tmp_path: Path) -> None:
    _tree(tmp_path, {"d/a.yaml": CONFIGMAP, "d/env/b.yaml": CONFIGMAP, "d/config.yaml": CONFIGMAP})
    found = directory_files(tmp_path, "d", {"recurse": True, "include": "*.yaml", "exclude": "{config.yaml,env/*}"})
    assert found == {"d/a.yaml"}


@pytest.mark.static
def test_directory_honours_skip_file_rendering_marker(tmp_path: Path) -> None:
    _tree(tmp_path, {
        "d/a.yaml": CONFIGMAP,
        "d/b.yaml": "# +argocd:skip-file-rendering\n" + yaml.safe_dump(CONFIGMAP),
    })
    assert directory_files(tmp_path, "d", {}) == {"d/a.yaml"}


@pytest.mark.static
def test_directory_source_path_naming_nothing_raises(tmp_path: Path) -> None:
    manifests = _tree(tmp_path, {"gitops/apps/x.yaml": _app("x", "missing", directory={"recurse": True})})
    with pytest.raises(FileNotFoundError, match="missing"):
        synced_paths(tmp_path, manifests)


# --- source type detection (explicit block, then the path's files) --------------


@pytest.mark.static
def test_path_without_kustomization_or_chart_is_a_directory(tmp_path: Path) -> None:
    """The namespaces app's shape: no directory block, ArgoCD detects Directory, recurse off."""
    manifests = _tree(tmp_path, {
        "d/a.yaml": CONFIGMAP,
        "d/sub/b.yaml": CONFIGMAP,
        "gitops/apps/x.yaml": _app("x", "d"),
    })
    assert source_type(tmp_path, {"path": "d"}) == "Directory"
    assert synced_paths(tmp_path, manifests) == {"d/a.yaml"}


@pytest.mark.static
def test_path_with_kustomization_renders_only_its_resources(tmp_path: Path) -> None:
    manifests = _tree(tmp_path, {
        "k/kustomization.yaml": {"resources": ["cm.yaml"]},
        "k/cm.yaml": CONFIGMAP,
        "k/stray.yaml": CONFIGMAP,
        "gitops/apps/x.yaml": _app("x", "k"),
    })
    assert source_type(tmp_path, {"path": "k"}) == "Kustomize"
    assert synced_paths(tmp_path, manifests) == {"k/cm.yaml"}


@pytest.mark.static
def test_directory_block_on_kustomization_reads_files_not_resources(tmp_path: Path) -> None:
    """ArgoCD takes the explicit type (#76): the kustomization's resources outside the path never sync."""
    manifests = _tree(tmp_path, {
        "k/kustomization.yaml": {"resources": ["../other/cm.yaml"]},
        "other/cm.yaml": CONFIGMAP,
        "gitops/apps/x.yaml": _app("x", "k", directory={"recurse": True}),
    })
    assert source_type(tmp_path, {"path": "k", "directory": {}}) == "Directory"
    assert synced_paths(tmp_path, manifests) == {"k/kustomization.yaml"}


@pytest.mark.static
def test_chart_sources_contribute_nothing(tmp_path: Path) -> None:
    manifests = _tree(tmp_path, {
        "c/Chart.yaml": {"apiVersion": "v2", "name": "c", "version": "0.1.0"},
        "c/templates/cm.yaml": CONFIGMAP,
        "gitops/apps/local.yaml": _app("local", "c"),
        "gitops/apps/remote.yaml": _app("remote", chart="kyverno", targetRevision="3.7.1", helm={}),
    })
    assert source_type(tmp_path, {"path": "c"}) == "Helm"
    assert source_type(tmp_path, {"chart": "kyverno"}) is None
    assert synced_paths(tmp_path, manifests) == set()


@pytest.mark.static
def test_two_explicit_types_raise(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="multiple"):
        source_type(tmp_path, {"path": "d", "directory": {}, "kustomize": {}})


# --- gobwas glob, as ArgoCD's glob.Match calls it (no separators) ----------------


@pytest.mark.static
@pytest.mark.parametrize(("pattern", "text", "matched"), [
    ("*.yaml", "a.yaml", True),
    ("*.yaml", "sub/a.yaml", True),
    ("*.yaml", "a.yml", False),
    ("{*.yml,*.yaml}", "a.yml", True),
    ("{config.json,env-usw2/*}", "env-usw2/deep/x.yaml", True),
    ("{config.json,env-usw2/*}", "config.yaml", False),
    ("a?.yaml", "ab.yaml", True),
    ("a?.yaml", "abc.yaml", False),
    ("[ab].yaml", "b.yaml", True),
    ("[!ab].yaml", "b.yaml", False),
    ("[a-c].yaml", "c.yaml", True),
    ("a.yaml", "a_yaml", False),
    (r"\*.yaml", "*.yaml", True),
    (r"\*.yaml", "x.yaml", False),
    ("**/x.yaml", "a/b/x.yaml", True),
])
def test_glob_match(pattern: str, text: str, matched: bool) -> None:
    assert glob_match(pattern, text) is matched


@pytest.mark.static
@pytest.mark.parametrize("pattern", ["[ab", "{a,b", "a\\"])
def test_glob_that_does_not_compile_raises(pattern: str) -> None:
    """ArgoCD logs and matches nothing, so the include or exclude silently stops working; fail instead."""
    with pytest.raises(ValueError, match="glob"):
        glob_match(pattern, "a")
