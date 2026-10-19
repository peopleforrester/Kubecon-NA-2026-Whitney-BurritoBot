# ABOUTME: An OTLP/gRPC receiver on a loopback port that keeps every trace and metric export it is sent.
# ABOUTME: The receiving end for tests that prove an app's SDK records and exports its telemetry over the wire.

from __future__ import annotations

import threading
from collections.abc import Iterator
from concurrent import futures
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any

import grpc
from opentelemetry.proto.collector.metrics.v1 import (
    metrics_service_pb2,
    metrics_service_pb2_grpc,
)
from opentelemetry.proto.collector.trace.v1 import (
    trace_service_pb2,
    trace_service_pb2_grpc,
)
from opentelemetry.proto.common.v1.common_pb2 import AnyValue, KeyValue


def any_value(value: AnyValue) -> Any:
    """The Python value an OTLP AnyValue carries."""
    kind = value.WhichOneof("value")
    return getattr(value, kind) if kind else None


def attributes(pairs: list[KeyValue]) -> dict[str, Any]:
    return {kv.key: any_value(kv.value) for kv in pairs}


@dataclass(frozen=True)
class ReceivedSpan:
    name: str
    kind: int
    status_code: int
    attributes: dict[str, Any]
    resource: dict[str, Any]
    trace_id: bytes
    parent_span_id: bytes


@dataclass(frozen=True)
class ReceivedPoint:
    """One data point of a received metric: histogram points carry a count, sums a value."""

    metric: str
    unit: str
    attributes: dict[str, Any]
    resource: dict[str, Any]
    count: int | None = None
    value: float | None = None


@dataclass
class Received:
    """What the receiver has been sent, decoded."""

    spans: list[ReceivedSpan] = field(default_factory=list)
    points: list[ReceivedPoint] = field(default_factory=list)
    lock: threading.Lock = field(default_factory=threading.Lock)

    def add_traces(self, request: trace_service_pb2.ExportTraceServiceRequest) -> None:
        with self.lock:
            for resource_spans in request.resource_spans:
                resource = attributes(resource_spans.resource.attributes)
                for scope_spans in resource_spans.scope_spans:
                    self.spans += [
                        ReceivedSpan(
                            name=span.name,
                            kind=span.kind,
                            status_code=span.status.code,
                            attributes=attributes(span.attributes),
                            resource=resource,
                            trace_id=span.trace_id,
                            parent_span_id=span.parent_span_id,
                        )
                        for span in scope_spans.spans
                    ]

    def add_metrics(self, request: metrics_service_pb2.ExportMetricsServiceRequest) -> None:
        with self.lock:
            for resource_metrics in request.resource_metrics:
                resource = attributes(resource_metrics.resource.attributes)
                for scope_metrics in resource_metrics.scope_metrics:
                    for metric in scope_metrics.metrics:
                        kind = metric.WhichOneof("data")
                        for point in getattr(metric, kind).data_points:
                            self.points.append(
                                ReceivedPoint(
                                    metric=metric.name,
                                    unit=metric.unit,
                                    attributes=attributes(point.attributes),
                                    resource=resource,
                                    count=point.count if kind == "histogram" else None,
                                    value=(point.as_int or point.as_double) if kind == "sum" else None,
                                )
                            )


class _Traces(trace_service_pb2_grpc.TraceServiceServicer):
    def __init__(self, received: Received) -> None:
        self.received = received

    def Export(self, request, context):  # noqa: N802 - the generated servicer's method name
        self.received.add_traces(request)
        return trace_service_pb2.ExportTraceServiceResponse()


class _Metrics(metrics_service_pb2_grpc.MetricsServiceServicer):
    def __init__(self, received: Received) -> None:
        self.received = received

    def Export(self, request, context):  # noqa: N802 - the generated servicer's method name
        self.received.add_metrics(request)
        return metrics_service_pb2.ExportMetricsServiceResponse()


@contextmanager
def otlp_receiver() -> Iterator[tuple[str, Received]]:
    """Serve OTLP/gRPC traces and metrics on a loopback port; yield its http:// endpoint and what arrives."""
    received = Received()
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=4))
    trace_service_pb2_grpc.add_TraceServiceServicer_to_server(_Traces(received), server)
    metrics_service_pb2_grpc.add_MetricsServiceServicer_to_server(_Metrics(received), server)
    port = server.add_insecure_port("127.0.0.1:0")
    server.start()
    try:
        yield f"http://127.0.0.1:{port}", received
    finally:
        server.stop(grace=None)
