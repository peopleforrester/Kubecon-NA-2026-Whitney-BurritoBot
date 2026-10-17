# ABOUTME: The telemetry path from BurritBot and the guardrails adapter to Grafana holds together (#101).
# ABOUTME: Collector Service, egress, GenAI span counts, and every dashboard query against what is actually emitted.

from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path
from types import ModuleType
from urllib.parse import urlsplit

import httpx
import pytest
import yaml
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import InMemoryMetricReader

from conftest import PROJECT_ROOT
from helpers.genai_telemetry import (
    COLLECTOR_SELF_METRICS,
    COUNT_CONNECTOR,
    DASHBOARDS,
    collector_service,
    collector_values,
    conformance_score_expr,
    dashboards,
    expected_count_spans,
    histogram_series,
    panel_targets,
    prometheus_name,
    prometheus_namespace,
    promql_metric_names,
)


BURRITBOT_APP = PROJECT_ROOT / "apps" / "burritbot" / "app.py"
ADAPTER = PROJECT_ROOT / "ai-gateway" / "extproc" / "adapter.py"
TEMPLATE = PROJECT_ROOT / "observability" / "otel-collector" / "config.yaml"
NETWORK_POLICY = PROJECT_ROOT / "security" / "kyverno" / "policies" / "restrict-burritbot-network.yaml"
PROMETHEUS_APP = PROJECT_ROOT / "gitops" / "apps" / "prometheus.yaml"
BURRITBOT_DEPLOYMENTS = sorted((PROJECT_ROOT / "apps" / "burritbot" / "k8s").glob("deployment-*.yaml"))
# The chart labels the collector's pods with its own name and the release's.
COLLECTOR_POD_NAME = "opentelemetry-collector"
OTLP_PORTS = {"otlp": 4317, "otlp-http": 4318}
# Labels every series carries: the resource (resource_to_telemetry_conversion) and histogram buckets.
RESOURCE_LABELS = {"service_name", "job", "le", "k8s_namespace_name", "k8s_pod_name"}


def _load(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader, f"cannot load {path}"
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _label(key: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_]", "_", key)


def _adapter_refusal_labels() -> set[str]:
    """The attribute keys the adapter puts on a refusal, read from a real count."""
    adapter = _load("burritbot_extproc_adapter_contract", ADAPTER)
    reader = InMemoryMetricReader()
    meter = MeterProvider(metric_readers=[reader]).get_meter("contract")
    processor = adapter.GuardrailsProcessor(adapter.LlmGuard(httpx.AsyncClient()), meter)
    processor._counted(adapter.refusal(adapter.StatusCode.Forbidden, "no"), "prompt")
    metrics = reader.get_metrics_data().resource_metrics[0].scope_metrics[0].metrics
    assert [m.name for m in metrics] == [adapter.REFUSALS]
    return {_label(k) for k in metrics[0].data.data_points[0].attributes}


def emitted_series() -> set[str]:
    """Every Prometheus metric name the platform writes, derived from the code and the collector values."""
    burritbot = _load("burritbot_app_contract", BURRITBOT_APP)
    adapter = _load("burritbot_extproc_adapter_series", ADAPTER)
    series = histogram_series(prometheus_name(burritbot.OPERATION_DURATION, "s"))
    series |= histogram_series(prometheus_name(burritbot.TOKEN_USAGE, "{token}"))
    series.add(prometheus_name(adapter.REFUSALS, "{refusal}", monotonic_sum=True))
    series |= {prometheus_name(name, "", monotonic_sum=True) for name in expected_count_spans()}
    series |= {f"{prometheus_namespace()}_{name}" for name in COLLECTOR_SELF_METRICS}
    return series


def emitted_labels() -> set[str]:
    burritbot = _load("burritbot_app_contract_labels", BURRITBOT_APP)
    labels = {_label(k) for k in burritbot.model_call_attributes()} | {"error_type", "gen_ai_token_type"}
    return labels | _adapter_refusal_labels() | RESOURCE_LABELS


def promql_labels(expr: str) -> set[str]:
    """Label names a PromQL expression matches on or groups by."""
    selectors = re.findall(r"\{([^}]*)\}", expr)
    names = {m for s in selectors for m in re.findall(r"([a-zA-Z_][a-zA-Z0-9_]*)\s*(?:=~|!~|!=|=)", s)}
    for group in re.findall(r"\b(?:by|without)\s*\(([^)]*)\)", expr):
        names |= {g.strip() for g in group.split(",") if g.strip()}
    return names


def unemitted(expr: str, series: set[str]) -> set[str]:
    return promql_metric_names(expr) - series


def _env_values(name: str) -> list[tuple[Path, str]]:
    found = []
    for top in ("apps", "ai-gateway"):
        for path in sorted((PROJECT_ROOT / top).rglob("*.yaml")):
            for doc in yaml.safe_load_all(path.read_text(encoding="utf-8")):
                if not (isinstance(doc, dict) and doc.get("kind") == "Deployment"):
                    continue
                for container in doc["spec"]["template"]["spec"]["containers"]:
                    found += [(path, e["value"]) for e in container.get("env", []) if e["name"] == name]
    return found


# --- the collector is reachable by the name every sender uses ----------------


@pytest.mark.static
def test_every_otlp_endpoint_is_the_collector_service() -> None:
    """The chart names the Service after fullnameOverride; unset, it was otel-collector-opentelemetry-collector."""
    name, namespace = collector_service()
    ports = collector_values()["ports"]
    served = {p["servicePort"] for key, p in ports.items() if key in OTLP_PORTS and p.get("enabled")}
    endpoints = _env_values("OTEL_EXPORTER_OTLP_ENDPOINT")
    assert len(endpoints) >= 6, f"expected BurritBot x2, both scanners and both adapters, got {endpoints}"
    for path, value in endpoints:
        url = urlsplit(value)
        assert url.hostname == f"{name}.{namespace}.svc.cluster.local", f"{path}: {value} is not the collector"
        assert url.port in served, f"{path}: {value} names a port the collector Service does not serve"


@pytest.mark.static
def test_remote_write_is_namespaced_and_writes_no_target_info() -> None:
    prw = collector_values()["config"]["exporters"]["prometheusremotewrite"]
    assert prw["namespace"] == "burritbot"
    assert prw["resource_to_telemetry_conversion"]["enabled"] is True
    assert prw["target_info"]["enabled"] is False, (
        "target_info samples from senders sharing a job land out of order; Prometheus then rejects the whole write"
    )


@pytest.mark.static
def test_collector_scrapes_its_own_telemetry() -> None:
    """The overview's spans/sec panel reads the collector's own metrics through the chart's self-scrape receiver."""
    metrics = collector_values()["config"]["service"]["pipelines"]["metrics"]
    assert "prometheus" in metrics["receivers"]


# --- GenAI span counts follow the registry and orbweaver ---------------------


@pytest.mark.static
def test_count_connector_conditions_follow_the_registry() -> None:
    spans = collector_values()["config"]["connectors"][COUNT_CONNECTOR]["spans"]
    assert {name: spec["conditions"] for name, spec in spans.items()} == expected_count_spans()


@pytest.mark.static
def test_count_connector_feeds_prometheus_as_cumulative() -> None:
    config = collector_values()["config"]
    pipelines = config["service"]["pipelines"]
    assert COUNT_CONNECTOR in pipelines["traces"]["exporters"]
    genai = [p for p in pipelines.values() if COUNT_CONNECTOR in p["receivers"]]
    assert len(genai) == 1, "exactly one metrics pipeline takes the span counts"
    assert "deltatocumulative" in genai[0]["processors"], "the counts are delta; remote write drops delta sums"
    assert "deltatocumulative" in config["processors"]
    assert genai[0]["exporters"] == ["prometheusremotewrite"]


def _constant_genai_inserts(config: dict) -> list[str]:
    """gen_ai.* constants stamped on telemetry that is not scoped to legacy llm.* spans, or in a metrics pipeline."""
    metric_processors = {
        p for name, pipe in config["service"]["pipelines"].items() if name.startswith("metrics")
        for p in pipe["processors"]
    }
    bad = []
    for name, proc in config["processors"].items():
        for action in (proc or {}).get("actions", []) or []:
            if not (action.get("key", "").startswith("gen_ai.") and "value" in action):
                continue
            scoped = [a.get("key") for a in ((proc.get("include") or {}).get("attributes") or [])]
            if "llm.model_name" not in scoped:
                bad.append(f"{name} stamps {action['key']} on every span")
            if name in metric_processors:
                bad.append(f"{name} stamps {action['key']} in a metrics pipeline")
    return bad


@pytest.mark.static
@pytest.mark.parametrize("source", ["values", "template"])
def test_no_unscoped_gen_ai_constant(source: str) -> None:
    config = collector_values()["config"] if source == "values" else yaml.safe_load(TEMPLATE.read_text())
    assert _constant_genai_inserts(config) == []


@pytest.mark.static
def test_mutation_unscoped_provider_insert_is_caught() -> None:
    config = collector_values()["config"]
    config["processors"]["attributes/genai"]["actions"].append(
        {"key": "gen_ai.provider.name", "value": "gcp.vertex_ai", "action": "insert"}
    )
    assert any("every span" in v for v in _constant_genai_inserts(config))


# --- guarded BurritBot may reach the collector --------------------------------


@pytest.mark.static
def test_guarded_egress_admits_the_collector() -> None:
    policy = yaml.safe_load(NETWORK_POLICY.read_text(encoding="utf-8"))
    egress = policy["spec"]["rules"][0]["generate"]["data"]["spec"]["egress"]
    name, namespace = collector_service()
    rules = [
        rule
        for rule in egress
        for peer in rule.get("to", [])
        if peer.get("namespaceSelector", {}).get("matchLabels", {}).get("kubernetes.io/metadata.name") == namespace
        and peer.get("podSelector", {}).get("matchLabels", {})
        == {"app.kubernetes.io/name": COLLECTOR_POD_NAME, "app.kubernetes.io/instance": name}
    ]
    assert rules, "the guarded egress lock drops BurritBot's OTLP export to the collector"
    assert {(p["protocol"], p["port"]) for r in rules for p in r["ports"]} == {("TCP", OTLP_PORTS["otlp"])}


# --- every dashboard query reads what is emitted ------------------------------


def _promql_targets() -> list[tuple[str, int, str]]:
    return [
        (file, panel["id"], target["expr"])
        for file, dashboard in dashboards().items()
        for panel, target in panel_targets(dashboard)
        if "expr" in target
    ]


@pytest.mark.static
def test_dashboard_metrics_are_emitted() -> None:
    series = emitted_series()
    missing = {(f, p, n) for f, p, expr in _promql_targets() for n in unemitted(expr, series)}
    assert not missing, f"dashboards query metrics nothing emits: {sorted(missing)}"


@pytest.mark.static
def test_dashboard_labels_are_emitted() -> None:
    labels = emitted_labels()
    missing = {(f, p, n) for f, p, expr in _promql_targets() for n in promql_labels(expr) - labels}
    assert not missing, f"dashboards match labels no emitted series carries: {sorted(missing)}"


@pytest.mark.static
@pytest.mark.parametrize(
    "expr",
    [
        "sum(rate(burritbot_llm_guard_block_total[1m])) by (scanner)",
        "sum(rate(burritbot_burritbot_unguarded_leak_total[1m]))",
        "max(burritbot_cast_net_current_target)",
        "avg(burritbot_genai_attribute_coverage_ratio) * 100",
        "burritbot_orbweaver_conformance_score",
        "histogram_quantile(0.95, sum(rate(burritbot_burritbot_request_duration_seconds_bucket[5m])) by (le, guarded))",
        "sum(rate(burritbot_otelcol_receiver_accepted_spans[1m]))",
    ],
)
def test_mutation_the_old_queries_are_caught(expr: str) -> None:
    """The queries #101 found are each refused, by metric name or by label."""
    assert unemitted(expr, emitted_series()) or promql_labels(expr) - emitted_labels()


@pytest.mark.static
def test_traceql_matches_burritbot_model_spans() -> None:
    burritbot = _load("burritbot_app_contract_traceql", BURRITBOT_APP)
    services = set()
    for path in BURRITBOT_DEPLOYMENTS:
        container = yaml.safe_load(path.read_text())["spec"]["template"]["spec"]["containers"][0]
        services.add(next(e["value"] for e in container["env"] if e["name"] == "OTEL_SERVICE_NAME"))
    queries = [
        t["query"] for d in dashboards().values() for _, t in panel_targets(d) if t.get("queryType") == "traceql"
    ]
    assert queries, "the traces dashboard has no TraceQL panel"
    for query in queries:
        operation = re.search(r'span\.gen_ai\.operation\.name\s*=\s*"([^"]+)"', query)
        assert operation and operation.group(1) == burritbot.GENAI_OPERATION, query
        pattern = re.search(r'resource\.service\.name\s*=~\s*"([^"]+)"', query)
        assert pattern and all(re.fullmatch(pattern.group(1), s) for s in services), (query, services)


@pytest.mark.static
def test_conformance_score_uses_orbweaver_weights() -> None:
    eyes = dashboards()["the-eyes-overview.json"]
    exprs = [t["expr"] for p, t in panel_targets(eyes) if "conformance" in p["title"]]
    assert exprs == [conformance_score_expr()]


@pytest.mark.static
@pytest.mark.parametrize("name", sorted(dashboards()))
def test_configmap_embeds_its_dashboard(name: str) -> None:
    configmap = yaml.safe_load((DASHBOARDS / name.replace(".json", "-configmap.yaml")).read_text(encoding="utf-8"))
    assert json.loads(configmap["data"][name]) == dashboards()[name]


@pytest.mark.static
def test_tempo_datasource_uid_matches_the_panels() -> None:
    values = yaml.safe_load(PROMETHEUS_APP.read_text())["spec"]["source"]["helm"]["valuesObject"]
    uids = {d["uid"] for d in values["grafana"]["additionalDataSources"] if d["type"] == "tempo"}
    used = {
        p["datasource"]["uid"]
        for d in dashboards().values()
        for p in d["panels"]
        if (p.get("datasource") or {}).get("type") == "tempo"
    }
    assert used and used <= uids, f"panels name Tempo uid {used}, Grafana provisions {uids}"
