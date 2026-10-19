# ABOUTME: Shared pytest fixtures for burritbot integration tests.
# ABOUTME: Provides Kubernetes clients, GCP clients, and project-wide constants.

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest


# --- Project constants (Rule: no hardcoded project IDs in shipped code;
# tests use these constants so they can be overridden via env vars for the
# real project ID before `terraform apply`) ---

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TERRAFORM_DIR = PROJECT_ROOT / "infrastructure" / "terraform"

GCP_PROJECT_ID = os.environ.get("GCP_PROJECT_ID", "burritbot-kubecon-2026")
GCP_REGION = os.environ.get("GCP_REGION", "us-west1")
CLUSTER_NAME = os.environ.get("CLUSTER_NAME", "burritbot")

# Gemini model pin — Gemini 3 Pro is the GA default for this demo.
# Do not regress to 1.5 (unsupported), 2.0 (retired), or 2.5 (retires
# 2026-10-16 — before any late-2026 demo day).
GEMINI_MODEL = os.environ.get("MODEL_NAME", "gemini-3-pro")

# Namespaces the platform must provision. Note `burritbot-net` (not
# `guardrails`) — the enforcement stack lives in its own namespace.
EXPECTED_NAMESPACES = [
    "argocd",
    "monitoring",
    "security",
    "burritbot-net",
    "burritbot-unguarded",
    "burritbot-guarded",
    "audience",
    "cert-manager",
    "external-secrets",
    "envoy-gateway-system",
    "envoy-ai-gateway-system",
]

# Grafana demo credentials (base64 of admin:admin) for wget in test pods.
GRAFANA_BASIC_AUTH = "Basic YWRtaW46YWRtaW4="


# --- Per-worktree temp dirs (issue #115) --------------------------------
#
# pytest's default basetemp is a numbered dir under the shared
# /tmp/pytest-of-<user>. Concurrent runs under one OS user share that dir,
# and when the host's /tmp runs out of inodes every tmp_path fails setup
# with "could not create numbered dir ... after 10 tries"; pytest's output
# capture in probe sessions fails the same way through `tempfile`. Each
# session keeps its temp files under its own rootdir instead, off /tmp:
# `basetemp/` for tmp_path (pytest clears it at session start) and `tmp/`
# as TMPDIR for `tempfile` here and in every subprocess. The dir is
# gitignored and skipped by the tree-walking tests.

WORKTREE_TMP_DIRNAME = ".pytest-tmp"


def worktree_basetemp(rootdir: Path) -> Path:
    """The basetemp for sessions rooted at `rootdir`: inside that worktree."""
    return rootdir.resolve() / WORKTREE_TMP_DIRNAME / "basetemp"


def worktree_tmpdir(rootdir: Path) -> Path:
    """The TMPDIR for sessions rooted at `rootdir`: inside that worktree."""
    return rootdir.resolve() / WORKTREE_TMP_DIRNAME / "tmp"


# The --basetemp and TMPDIR the session was started with, before
# pytest_configure fills them in; None where the caller gave none.
GIVEN_TEMP_DIRS = pytest.StashKey[tuple[str | None, str | None]]()


@pytest.fixture
def given_temp_dirs(pytestconfig: pytest.Config) -> tuple[str | None, str | None]:
    """The (--basetemp, TMPDIR) this session was started with, None where not given."""
    return pytestconfig.stash[GIVEN_TEMP_DIRS]


@pytest.hookimpl(tryfirst=True)
def pytest_configure(config: pytest.Config) -> None:
    """Keep this session's temp files in its worktree.

    Runs before pytest's tmpdir plugin reads --basetemp. A --basetemp
    given on the command line, or a TMPDIR already set, is left as given.
    Keyed on the session's rootdir, so a nested probe session rooted in
    its own tmp dir never clears the outer session's basetemp.
    """
    config.stash[GIVEN_TEMP_DIRS] = (config.option.basetemp, os.environ.get("TMPDIR") or None)
    if config.option.basetemp is None:
        basetemp = worktree_basetemp(config.rootpath)
        basetemp.parent.mkdir(exist_ok=True)
        config.option.basetemp = str(basetemp)
    if not os.environ.get("TMPDIR"):
        tmpdir = worktree_tmpdir(config.rootpath)
        tmpdir.mkdir(parents=True, exist_ok=True)
        os.environ["TMPDIR"] = str(tmpdir)
        tempfile.tempdir = str(tmpdir)


# --- Live-cluster fixtures ----------------------------------------------
#
# Tests decorated with @pytest.mark.live require a reachable GKE cluster and
# a loaded kubeconfig. Without one these fixtures fail the requesting test
# with a clear message: no skips, no fallbacks. Static tests never request
# them, so the light Test command runs on a bare workstation.


def _load_kubeconfig() -> None:
    """Load the kubeconfig, failing the requesting test when there is none."""
    from kubernetes import config  # type: ignore

    try:
        config.load_kube_config()
    except config.ConfigException as exc:
        pytest.fail(
            "kubeconfig not loaded; live cluster fixtures need one. Run "
            "`gcloud container clusters get-credentials` for the demo cluster "
            f"before `pytest -m live`: {exc}"
        )


@pytest.fixture(scope="session")
def k8s_core_v1():
    """CoreV1Api client for pod/service/namespace assertions.

    Fails explicitly if kubeconfig is not loaded (no fallbacks, no mocks).
    """
    _load_kubeconfig()
    from kubernetes import client  # type: ignore

    return client.CoreV1Api()


@pytest.fixture(scope="session")
def k8s_apps_v1():
    """AppsV1Api client for deployment/daemonset assertions."""
    _load_kubeconfig()
    from kubernetes import client  # type: ignore

    return client.AppsV1Api()


@pytest.fixture(scope="session")
def k8s_custom_objects():
    """CustomObjectsApi client for CRD assertions (Kyverno policies, etc.)."""
    _load_kubeconfig()
    from kubernetes import client  # type: ignore

    return client.CustomObjectsApi()


@pytest.fixture(scope="session")
def k8s_networking_v1():
    """NetworkingV1Api client for NetworkPolicy assertions."""
    _load_kubeconfig()
    from kubernetes import client  # type: ignore

    return client.NetworkingV1Api()


@pytest.fixture(scope="session")
def k8s_rbac_v1():
    """RbacAuthorizationV1Api client for RBAC assertions."""
    _load_kubeconfig()
    from kubernetes import client  # type: ignore

    return client.RbacAuthorizationV1Api()


@pytest.fixture(scope="session")
def k8s_apiextensions_v1():
    """ApiextensionsV1Api client for reading installed CRD schemas."""
    _load_kubeconfig()
    from kubernetes import client  # type: ignore

    return client.ApiextensionsV1Api()


# --- GCP client fixtures ------------------------------------------------


@pytest.fixture(scope="session")
def gcp_project_id() -> str:
    """Return the GCP project ID under test."""
    return GCP_PROJECT_ID


@pytest.fixture(scope="session")
def gcp_region() -> str:
    """Return the GCP region under test."""
    return GCP_REGION


@pytest.fixture(scope="session")
def cluster_name() -> str:
    """Return the GKE cluster name used throughout tests."""
    return CLUSTER_NAME


@pytest.fixture(scope="session")
def expected_namespaces() -> list[str]:
    """Return the list of namespaces the burritbot platform requires."""
    return list(EXPECTED_NAMESPACES)


@pytest.fixture(scope="session")
def gcp_container_client():
    """google-cloud-container ClusterManagerClient for GKE assertions."""
    from google.auth.exceptions import DefaultCredentialsError
    from google.cloud import container_v1  # type: ignore

    try:
        return container_v1.ClusterManagerClient()
    except DefaultCredentialsError as exc:
        pytest.fail(f"GCP auth unavailable; run `gcloud auth application-default login`: {exc}")


@pytest.fixture(scope="session")
def gcp_secret_manager_client():
    """google-cloud-secret-manager SecretManagerServiceClient."""
    from google.auth.exceptions import DefaultCredentialsError
    from google.cloud import secretmanager  # type: ignore

    try:
        return secretmanager.SecretManagerServiceClient()
    except DefaultCredentialsError as exc:
        pytest.fail(f"GCP auth unavailable; run `gcloud auth application-default login`: {exc}")
