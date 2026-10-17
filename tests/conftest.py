# ABOUTME: Shared pytest fixtures for burritbot integration tests.
# ABOUTME: Provides Kubernetes clients, GCP clients, and project-wide constants.

from __future__ import annotations

import os
import socket
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


# --- BurritBot's OTLP export ---------------------------------------------
#
# BurritBot refuses to start without OTEL_EXPORTER_OTLP_ENDPOINT and
# OTEL_SERVICE_NAME (apps/burritbot/app.py), and many tests import it for its
# constants and pure functions. They get an endpoint on a loopback port nothing
# listens on, so nothing they record leaves the host. The tests that prove the
# export (tests/test_burritbot_telemetry.py) point it at a real OTLP receiver,
# and the ones that prove the refusal unset it.


def closed_loopback_url() -> str:
    """An http URL on a loopback port nothing listens on."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    return f"http://127.0.0.1:{port}"


@pytest.fixture(autouse=True)
def _burritbot_otel_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", closed_loopback_url())
    monkeypatch.setenv("OTEL_SERVICE_NAME", "burritbot-tests")


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
