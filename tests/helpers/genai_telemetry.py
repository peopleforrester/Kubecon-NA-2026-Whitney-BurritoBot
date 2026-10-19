# ABOUTME: The GenAI telemetry contract derived from the repo: Weaver registry, orbweaver weights, collector values.
# ABOUTME: Names what reaches Prometheus and Tempo, so the dashboards are held to what the platform emits (#101).

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import yaml

from conftest import PROJECT_ROOT


OBSERVABILITY = PROJECT_ROOT / "observability"
REGISTRY = OBSERVABILITY / "otel-weaver" / "genai-semconv-registry.yaml"
ORBWEAVER = OBSERVABILITY / "spinybacked-orbweaver" / "config.yaml"
DASHBOARDS = OBSERVABILITY / "grafana" / "dashboards"
COLLECTOR_APP = PROJECT_ROOT / "gitops" / "apps" / "otel-collector.yaml"
COLLECTOR_CHART = "opentelemetry-collector"
COUNT_CONNECTOR = "count/genai"

# A span is a GenAI operation when it names one (semconv v1.37.0: required on
# every GenAI span). Only answered calls are scored: a failed call has no usage.
GENAI_SPAN = 'attributes["gen_ai.operation.name"] != nil and status.code != STATUS_CODE_ERROR'
SPANS = "burritbot.genai.spans"
CONFORMANT = "burritbot.genai.spans.conformant"
CONFORMING_PREFIX = "burritbot.genai.spans.conforming."

# OTLP -> Prometheus names, as the collector's prometheusremotewrite exporter
# writes them (default translation, checked against otelcol-contrib 0.145.0
# and Prometheus 3.7.3 when #101 landed): the exporter's namespace, the name
# with '.' as '_', the unit's suffix, and _total on a monotonic sum.
UNIT_SUFFIXES = {"s": "seconds", "By": "bytes", "1": "ratio"}

# Collector internal telemetry the overview dashboard reads, as the chart's
# self-scrape receiver (`prometheus`, job opentelemetry-collector) sees it.
COLLECTOR_SELF_METRICS = {"otelcol_receiver_accepted_spans_total"}


def registry_attributes() -> dict[str, dict[str, Any]]:
    """Every attribute the Weaver registry declares, by id."""
    doc = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))
    return {attr["id"]: attr for group in doc["groups"] for attr in group.get("attributes", [])}


def required_attributes() -> list[str]:
    return [a for a, spec in registry_attributes().items() if spec["requirement_level"] == "required"]


def orbweaver_weights() -> dict[str, float]:
    return {k: float(v) for k, v in yaml.safe_load(ORBWEAVER.read_text(encoding="utf-8"))["weights"].items()}


def conforms(attribute: str) -> str:
    """The OTTL condition for a span attribute that conforms to the registry: its type, or one of its members."""
    spec = registry_attributes()[attribute]
    ref = f'attributes["{attribute}"]'
    kind = spec["type"]
    if isinstance(kind, dict):
        members = " or ".join(f'{ref} == "{m["value"]}"' for m in kind["members"])
        return f"({members})"
    converter = {"string": "IsString", "int": "IsInt", "boolean": "IsBool", "double": "IsDouble"}[kind]
    return f"{converter}({ref})"


def expected_count_spans() -> dict[str, list[str]]:
    """The count connector's span metrics, name -> conditions, as the registry and weights define them."""
    metrics = {
        SPANS: [GENAI_SPAN],
        CONFORMANT: [" and ".join([GENAI_SPAN, *(conforms(a) for a in required_attributes())])],
    }
    for attribute in orbweaver_weights():
        metrics[CONFORMING_PREFIX + attribute] = [f"{GENAI_SPAN} and {conforms(attribute)}"]
    return metrics


def collector_values() -> dict[str, Any]:
    doc = yaml.safe_load(COLLECTOR_APP.read_text(encoding="utf-8"))
    return doc["spec"]["source"]["helm"]["valuesObject"]


def collector_service() -> tuple[str, str]:
    """The collector Service's (name, namespace): the chart names it after fullnameOverride."""
    doc = yaml.safe_load(COLLECTOR_APP.read_text(encoding="utf-8"))
    return collector_values()["fullnameOverride"], doc["spec"]["destination"]["namespace"]


def prometheus_namespace() -> str:
    return collector_values()["config"]["exporters"]["prometheusremotewrite"]["namespace"]


def prometheus_name(otel_name: str, unit: str, monotonic_sum: bool = False) -> str:
    """The name an OTLP metric is written to Prometheus under, before any _bucket/_count/_sum."""
    parts = [prometheus_namespace(), re.sub(r"[^a-zA-Z0-9_]", "_", otel_name)]
    suffix = UNIT_SUFFIXES.get(unit, "" if unit.startswith("{") or not unit else unit)
    if suffix:
        parts.append(suffix)
    if monotonic_sum:
        parts.append("total")
    return "_".join(parts)


def histogram_series(base: str) -> set[str]:
    return {f"{base}_bucket", f"{base}_count", f"{base}_sum"}


def dashboards() -> dict[str, dict[str, Any]]:
    return {p.name: json.loads(p.read_text(encoding="utf-8")) for p in sorted(DASHBOARDS.glob("*.json"))}


def panel_targets(dashboard: dict[str, Any]) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    return [(panel, target) for panel in dashboard.get("panels", []) for target in panel.get("targets", [])]


PROMQL_KEYWORDS = {
    "sum", "rate", "by", "without", "histogram_quantile", "le", "or", "and", "unless", "vector", "max", "min",
    "avg", "count", "on", "ignoring", "group_left", "group_right", "bool", "offset", "clamp_max", "clamp_min",
    "increase", "irate", "topk", "bottomk", "abs", "scalar", "time",
}


def promql_metric_names(expr: str) -> set[str]:
    """The metric names a PromQL expression selects: identifiers outside {} and [] that are not functions or labels."""
    bare = re.sub(r"\{[^}]*\}", "", re.sub(r"\[[^\]]*\]", "", expr))
    bare = re.sub(r"\b(by|without|on|ignoring)\s*\([^)]*\)", "", bare)
    bare = re.sub(r'"[^"]*"', "", bare)
    names = set(re.findall(r"\b[a-zA-Z_:][a-zA-Z0-9_:]*\b", bare))
    return {n for n in names if n not in PROMQL_KEYWORDS and not re.fullmatch(r"\d+(\.\d+)?|e\d+", n)}


def conformance_score_expr(window: str = "5m") -> str:
    """orbweaver's weighted score over the conforming-span counts: 1.0 when every weighted attribute conforms."""
    weights = orbweaver_weights()
    total = sum(weights.values())

    def rate(metric: str) -> str:
        return f"(sum(rate({prometheus_name(metric, '', monotonic_sum=True)}[{window}])) or vector(0))"

    numerator = " + ".join(f"{w:g} * {rate(CONFORMING_PREFIX + a)}" for a, w in weights.items())
    return f"({numerator}) / ({total:g} * sum(rate({prometheus_name(SPANS, '', monotonic_sum=True)}[{window}])))"


def dashboard_file(name: str) -> Path:
    return DASHBOARDS / name
