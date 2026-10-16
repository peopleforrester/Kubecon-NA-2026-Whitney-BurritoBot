# ABOUTME: Phase 7 audience frontend tests — FastAPI backend and cast-net.sh toggle.
# ABOUTME: Validates rate limiting, namespace enum, and the live Envoy route switch.

from __future__ import annotations

import stat

import pytest
import yaml

from conftest import PROJECT_ROOT


pytestmark = pytest.mark.phase7

FRONTEND_DIR = PROJECT_ROOT / "apps" / "audience-frontend"
BACKEND_FILE = FRONTEND_DIR / "backend" / "main.py"
FRONTEND_MANIFESTS = FRONTEND_DIR / "k8s"

SCRIPTS_DIR = PROJECT_ROOT / "scripts"
CAST_NET_SCRIPT = SCRIPTS_DIR / "cast-net.sh"


@pytest.mark.static
def test_audience_frontend_tree_exists() -> None:
    assert FRONTEND_DIR.is_dir(), "apps/audience-frontend/ is missing"
    assert BACKEND_FILE.exists(), "apps/audience-frontend/backend/main.py is missing"
    assert FRONTEND_MANIFESTS.is_dir(), "apps/audience-frontend/k8s/ is missing"


@pytest.mark.static
def test_backend_uses_fastapi() -> None:
    """Audience backend is a FastAPI app."""
    text = BACKEND_FILE.read_text(encoding="utf-8")
    assert "from fastapi" in text or "import fastapi" in text, (
        "audience backend does not import FastAPI"
    )
    assert "FastAPI(" in text, "audience backend never instantiates FastAPI()"


@pytest.mark.static
def test_backend_enforces_rate_limit() -> None:
    """Audience backend limits /chat per browser token, under a per-address ceiling (question 157).

    The numbers are settings; tests/test_phase_07_browser_token.py holds the
    delivery overlay to 10/minute per token and 300/minute per address.
    """
    text = BACKEND_FILE.read_text(encoding="utf-8")
    for setting in ("AUDIENCE_TOKEN_LIMIT", "AUDIENCE_ADDRESS_LIMIT", "X-Audience-Token"):
        assert setting in text, f"audience backend does not read {setting}"
    assert "@limiter.limit(" in text, "audience backend never limits a route"


@pytest.mark.static
def test_backend_declares_burritbot_targets() -> None:
    """Backend knows how to proxy to both unguarded and guarded BurritBot."""
    text = BACKEND_FILE.read_text(encoding="utf-8")
    assert "burritbot-unguarded" in text, (
        "backend has no reference to burritbot-unguarded"
    )
    assert "burritbot-guarded" in text, (
        "backend has no reference to burritbot-guarded"
    )


@pytest.mark.static
def test_cast_net_script_exists_and_is_executable() -> None:
    """scripts/cast-net.sh exists, is marked executable, and has ABOUTME."""
    assert CAST_NET_SCRIPT.exists(), "scripts/cast-net.sh is missing"
    mode = CAST_NET_SCRIPT.stat().st_mode
    assert mode & stat.S_IXUSR, "scripts/cast-net.sh is not executable"
    text = CAST_NET_SCRIPT.read_text(encoding="utf-8")
    first_lines = text.splitlines()[:4]
    aboutme_count = sum(1 for ln in first_lines if "ABOUTME:" in ln)
    assert aboutme_count >= 2, "cast-net.sh missing ABOUTME lines"


@pytest.mark.static
def test_cast_net_script_toggles_between_targets() -> None:
    """cast-net.sh references both unguarded and guarded targets."""
    text = CAST_NET_SCRIPT.read_text(encoding="utf-8")
    assert "burritbot-unguarded" in text, "cast-net.sh missing unguarded target"
    assert "burritbot-guarded" in text, "cast-net.sh missing guarded target"


@pytest.mark.static
def test_frontend_deployment_targets_audience_namespace() -> None:
    """Audience frontend Deployment lives in the `audience` namespace."""
    deploy = FRONTEND_MANIFESTS / "deployment.yaml"
    assert deploy.exists(), "apps/audience-frontend/k8s/deployment.yaml is missing"
    doc = yaml.safe_load(deploy.read_text(encoding="utf-8"))
    assert doc["kind"] == "Deployment", "deployment.yaml is not a Deployment"
    assert doc["metadata"]["namespace"] == "audience", (
        "audience frontend is not in the `audience` namespace"
    )


# --- Live frontend checks ---------------------------------------------------


@pytest.mark.live
def test_audience_frontend_pod_running(k8s_core_v1) -> None:
    pods = k8s_core_v1.list_namespaced_pod(
        namespace="audience",
        label_selector="app.kubernetes.io/name=audience-frontend",
    )
    running = [p for p in pods.items if p.status and p.status.phase == "Running"]
    assert running, "No audience-frontend pods Running"
