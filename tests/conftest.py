# ABOUTME: Shared pytest fixtures for burritbot integration tests.
# ABOUTME: Provides Kubernetes clients, GCP clients, and project-wide constants.

from __future__ import annotations

import os
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
]

# Grafana demo credentials (base64 of admin:admin) for wget in test pods.
GRAFANA_BASIC_AUTH = "Basic YWRtaW46YWRtaW4="


# --- Live-cluster fixtures --------------------------------------------
#
# Tests decorated with @pytest.mark.live require a reachable GKE cluster and
# a loaded kubeconfig. They run only under the E2E command (`pytest -m
# live`); the Test command (`pytest -m static`) never requests these
# fixtures. A missing kubeconfig, client library or credential fails the
# test with a message naming what is missing.


def _kube_client():
    """Load kubeconfig and return the kubernetes client module, or fail loudly."""
    try:
        from kubernetes import client, config  # type: ignore
    except ImportError as exc:
        pytest.fail(f"live test needs the kubernetes client library: {exc}")
    try:
        config.load_kube_config()
    except Exception as exc:
        pytest.fail(
            f"live test needs a kubeconfig for the burritbot cluster "
            f"(run `gcloud container clusters get-credentials`): {exc}"
        )
    return client


@pytest.fixture(scope="session")
def k8s_core_v1():
    """CoreV1Api client for pod/service/namespace assertions."""
    return _kube_client().CoreV1Api()


@pytest.fixture(scope="session")
def k8s_apps_v1():
    """AppsV1Api client for deployment/daemonset assertions."""
    return _kube_client().AppsV1Api()


@pytest.fixture(scope="session")
def k8s_custom_objects():
    """CustomObjectsApi client for CRD assertions (Kyverno policies, etc.)."""
    return _kube_client().CustomObjectsApi()


@pytest.fixture(scope="session")
def k8s_networking_v1():
    """NetworkingV1Api client for NetworkPolicy assertions."""
    return _kube_client().NetworkingV1Api()


@pytest.fixture(scope="session")
def k8s_rbac_v1():
    """RbacAuthorizationV1Api client for RBAC assertions."""
    return _kube_client().RbacAuthorizationV1Api()


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
    try:
        from google.cloud import container_v1  # type: ignore
    except ImportError as exc:
        pytest.fail(f"live test needs google-cloud-container: {exc}")
    try:
        return container_v1.ClusterManagerClient()
    except Exception as exc:
        pytest.fail(
            f"live test needs GCP Application Default Credentials "
            f"(run `gcloud auth application-default login`): {exc}"
        )


@pytest.fixture(scope="session")
def gcp_secret_manager_client():
    """google-cloud-secret-manager SecretManagerServiceClient."""
    try:
        from google.cloud import secretmanager  # type: ignore
    except ImportError as exc:
        pytest.fail(f"live test needs google-cloud-secret-manager: {exc}")
    try:
        return secretmanager.SecretManagerServiceClient()
    except Exception as exc:
        pytest.fail(
            f"live test needs GCP Application Default Credentials "
            f"(run `gcloud auth application-default login`): {exc}"
        )
