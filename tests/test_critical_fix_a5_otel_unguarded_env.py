# ABOUTME: Phase A5 test — unguarded BurritBot deployment must export OTEL_* env so the
# ABOUTME: cast-net comparison dashboard can plot guarded vs unguarded latency side-by-side.

from __future__ import annotations

import pytest
import yaml

from conftest import PROJECT_ROOT


UNGUARDED_DEPLOYMENT = (
    PROJECT_ROOT / "apps" / "burritbot" / "k8s" / "deployment-unguarded.yaml"
)


def _container_env(deployment: dict, container_name: str) -> dict[str, str]:
    """Return env-var name -> value dict for the named container."""
    containers = deployment["spec"]["template"]["spec"]["containers"]
    container = next(c for c in containers if c["name"] == container_name)
    return {e["name"]: e.get("value", "") for e in container.get("env", [])}


@pytest.mark.static
def test_unguarded_deployment_exports_otel_endpoint() -> None:
    deployment = yaml.safe_load(UNGUARDED_DEPLOYMENT.read_text())
    env = _container_env(deployment, "burritbot")
    assert "OTEL_EXPORTER_OTLP_ENDPOINT" in env, (
        "unguarded BurritBot has no OTEL_EXPORTER_OTLP_ENDPOINT — its spans "
        "will never reach the collector and Act 2's comparison view will be "
        "half-empty"
    )


@pytest.mark.static
def test_unguarded_deployment_sets_otel_service_name() -> None:
    deployment = yaml.safe_load(UNGUARDED_DEPLOYMENT.read_text())
    env = _container_env(deployment, "burritbot")
    assert env.get("OTEL_SERVICE_NAME") == "burritbot-unguarded", (
        f"OTEL_SERVICE_NAME must be 'burritbot-unguarded' to distinguish from "
        f"the guarded service in dashboards; got {env.get('OTEL_SERVICE_NAME')!r}"
    )
