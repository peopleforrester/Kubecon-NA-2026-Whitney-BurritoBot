# ABOUTME: Live-cluster and GCP fixtures in conftest.py must error, not pass quietly, when unavailable.
# ABOUTME: Runs a probe suite in a subprocess with no kubeconfig and no ADC and reads the outcome.

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import PROJECT_ROOT


# Each live fixture and the command its failure message must name.
LIVE_FIXTURES = {
    "k8s_core_v1": "gcloud container clusters get-credentials",
    "k8s_apps_v1": "gcloud container clusters get-credentials",
    "k8s_custom_objects": "gcloud container clusters get-credentials",
    "k8s_networking_v1": "gcloud container clusters get-credentials",
    "k8s_rbac_v1": "gcloud container clusters get-credentials",
    "k8s_apiextensions_v1": "gcloud container clusters get-credentials",
    "gcp_container_client": "gcloud auth application-default login",
    "gcp_secret_manager_client": "gcloud auth application-default login",
}


def _run_probe(tmp_path: Path, fixture: str) -> subprocess.CompletedProcess[str]:
    """Run one probe test that requests `fixture` with the cluster and ADC absent."""
    probe = tmp_path / f"test_probe_{fixture}.py"
    probe.write_text(f"def test_probe({fixture}):\n    pass\n")
    env = {
        k: v
        for k, v in os.environ.items()
        if k not in {"KUBERNETES_SERVICE_HOST", "KUBERNETES_SERVICE_PORT"}
    }
    env["KUBECONFIG"] = str(tmp_path / "missing-kubeconfig")
    env["GOOGLE_APPLICATION_CREDENTIALS"] = str(tmp_path / "missing-adc.json")
    env["PYTHONPATH"] = str(PROJECT_ROOT / "tests")
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-p",
            "conftest",
            "-p",
            "no:cacheprovider",
            "--rootdir",
            str(tmp_path),
            "-rA",
            str(probe),
        ],
        check=False,
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=90,
    )


@pytest.mark.static
@pytest.mark.parametrize("fixture", LIVE_FIXTURES)
def test_live_fixture_errors_when_unavailable(tmp_path: Path, fixture: str) -> None:
    """A missing cluster or missing GCP auth is a loud setup error naming the fix."""
    result = _run_probe(tmp_path, fixture)
    output = result.stdout + result.stderr
    assert result.returncode != 0, (
        f"{fixture} let the probe pass with no cluster / no ADC:\n{output}"
    )
    assert "1 error" in output, f"{fixture} did not error in setup:\n{output}"
    assert LIVE_FIXTURES[fixture] in output, (
        f"{fixture} failed without naming `{LIVE_FIXTURES[fixture]}`:\n{output}"
    )
