# ABOUTME: Phase 3 "The Eyes" tests — Prometheus, Grafana, OTel Collector, spinybacked-orbweaver.
# ABOUTME: Validates GenAI semantic convention processors and the three demo dashboards.

from __future__ import annotations

import json

import pytest
import yaml

from conftest import PROJECT_ROOT


pytestmark = pytest.mark.phase3

OBS_DIR = PROJECT_ROOT / "observability"
OTEL_CONFIG = OBS_DIR / "otel-collector" / "config.yaml"
WEAVER_REGISTRY = OBS_DIR / "otel-weaver" / "genai-semconv-registry.yaml"
ORBWEAVER_CONFIG = OBS_DIR / "spinybacked-orbweaver" / "config.yaml"
DASHBOARDS_DIR = OBS_DIR / "grafana" / "dashboards"

GEN_AI_ATTRIBUTES = {
    # Renamed in OTel semantic conventions v1.37.0 — `gen_ai.system` is
    # deprecated in favor of `gen_ai.provider.name`. Value `vertex_ai`
    # became `gcp.vertex_ai` at the same time.
    "gen_ai.provider.name",
    "gen_ai.request.model",
    "gen_ai.usage.input_tokens",
    "gen_ai.usage.output_tokens",
}


@pytest.mark.static
def test_otel_collector_forbids_deprecated_gen_ai_system() -> None:
    """Hard-forbid the deprecated `gen_ai.system` key so we cannot regress."""
    text = OTEL_CONFIG.read_text(encoding="utf-8")
    assert "gen_ai.system" not in text, (
        "otel-collector/config.yaml still references the deprecated "
        "`gen_ai.system` attribute (renamed to `gen_ai.provider.name` in "
        "OTel semconv v1.37.0)"
    )


@pytest.mark.static
def test_observability_tree_exists() -> None:
    assert OBS_DIR.is_dir(), "observability/ is missing"
    assert (OBS_DIR / "otel-collector").is_dir()
    assert (OBS_DIR / "otel-weaver").is_dir()
    assert (OBS_DIR / "spinybacked-orbweaver").is_dir()
    assert DASHBOARDS_DIR.is_dir()


@pytest.mark.static
def test_otel_collector_has_genai_processors() -> None:
    """OTel Collector config declares the gen_ai.* attribute processors."""
    assert OTEL_CONFIG.exists(), "otel-collector/config.yaml missing"
    doc = yaml.safe_load(OTEL_CONFIG.read_text(encoding="utf-8"))
    processors = doc.get("processors", {})
    attributes = processors.get("attributes", {})
    actions = attributes.get("actions", [])
    keys = {a.get("key") for a in actions}
    missing = GEN_AI_ATTRIBUTES - keys
    assert not missing, f"OTel attributes processor missing keys: {sorted(missing)}"


@pytest.mark.static
def test_otel_collector_exports_prometheus_and_grafana() -> None:
    doc = yaml.safe_load(OTEL_CONFIG.read_text(encoding="utf-8"))
    exporters = doc.get("exporters", {})
    assert "prometheus" in exporters, "prometheus exporter missing"
    assert any(name.startswith("otlp") for name in exporters), "No otlp exporter configured"


@pytest.mark.static
def test_genai_semconv_registry_valid_yaml() -> None:
    """OTel Weaver semantic convention registry is valid YAML with groups."""
    assert WEAVER_REGISTRY.exists(), "otel-weaver/genai-semconv-registry.yaml missing"
    doc = yaml.safe_load(WEAVER_REGISTRY.read_text(encoding="utf-8"))
    assert "groups" in doc, "Weaver registry must declare `groups`"


@pytest.mark.static
def test_spinybacked_orbweaver_config_exists() -> None:
    """spinybacked-orbweaver config pins registry path and score threshold."""
    assert ORBWEAVER_CONFIG.exists(), "spinybacked-orbweaver/config.yaml missing"
    doc = yaml.safe_load(ORBWEAVER_CONFIG.read_text(encoding="utf-8"))
    assert "registry" in doc, "orbweaver config missing `registry`"
    assert "score_threshold" in doc, "orbweaver config missing `score_threshold`"


@pytest.mark.static
def test_three_demo_dashboards_exist() -> None:
    """The three named demo dashboards exist as valid JSON files."""
    required = {
        "the-eyes-overview.json",
        "prompt-response-traces.json",
        "cast-net-comparison.json",
    }
    present = {p.name for p in DASHBOARDS_DIR.glob("*.json")}
    missing = required - present
    assert not missing, f"Missing demo dashboards: {sorted(missing)}"
    for name in required:
        path = DASHBOARDS_DIR / name
        data = json.loads(path.read_text(encoding="utf-8"))
        assert isinstance(data, dict), f"{name} is not a JSON object"
        assert "title" in data, f"{name} has no title field"


# --- Live Eyes checks -------------------------------------------------------


@pytest.mark.live
def test_otel_collector_pod_running(k8s_core_v1) -> None:
    pods = k8s_core_v1.list_namespaced_pod(
        namespace="monitoring",
        label_selector="app.kubernetes.io/name=opentelemetry-collector",
    )
    running = [p for p in pods.items if p.status and p.status.phase == "Running"]
    assert running, "No OTel Collector pods Running"


@pytest.mark.live
def test_grafana_pod_running(k8s_core_v1) -> None:
    pods = k8s_core_v1.list_namespaced_pod(
        namespace="monitoring",
        label_selector="app.kubernetes.io/name=grafana",
    )
    running = [p for p in pods.items if p.status and p.status.phase == "Running"]
    assert running, "No Grafana pods Running"
