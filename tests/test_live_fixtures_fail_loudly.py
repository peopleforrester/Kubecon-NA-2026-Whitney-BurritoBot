# ABOUTME: Live-cluster and GCP fixtures in conftest.py must fail, never skip, when unavailable.
# ABOUTME: Runs a probe suite in a subprocess with no kubeconfig and no ADC and reads the outcome.

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import PROJECT_ROOT


LIVE_FIXTURES = [
    "k8s_core_v1",
    "k8s_apps_v1",
    "k8s_custom_objects",
    "k8s_networking_v1",
    "k8s_rbac_v1",
    "gcp_container_client",
    "gcp_secret_manager_client",
]


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
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=90,
    )


@pytest.mark.static
@pytest.mark.parametrize("fixture", LIVE_FIXTURES)
def test_live_fixture_errors_instead_of_skipping(tmp_path: Path, fixture: str) -> None:
    """A missing cluster or missing GCP auth is a loud failure, not a skip."""
    result = _run_probe(tmp_path, fixture)
    output = result.stdout + result.stderr
    assert result.returncode != 0, (
        f"{fixture} let the probe pass with no cluster / no ADC:\n{output}"
    )
    assert "skipped" not in output.lower(), f"{fixture} skipped:\n{output}"
    assert "1 error" in output, f"{fixture} did not error in setup:\n{output}"


@pytest.mark.static
def test_conftest_has_no_skip_paths() -> None:
    """conftest.py carries no skip or importorskip call for any fixture."""
    text = (PROJECT_ROOT / "tests" / "conftest.py").read_text()
    for needle in ("pytest.skip(", "importorskip(", "pytest.xfail("):
        assert needle not in text, f"tests/conftest.py still calls {needle}"
