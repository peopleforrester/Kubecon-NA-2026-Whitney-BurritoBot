# ABOUTME: BurritBot FastAPI application — Chipotle-inspired chatbot backed by Vertex AI.
# ABOUTME: Model pin: gemini-3-pro (GA); unguarded via google-genai, guarded via the AI gateway.

from __future__ import annotations

import json
import logging
import os
import re
import time
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException, status
from fastapi.responses import JSONResponse
from google import genai
from google.genai import types
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.metrics import Histogram
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace import SpanKind, Status, StatusCode, Tracer
from pydantic import BaseModel, Field


logger = logging.getLogger("burritbot")
logging.basicConfig(level=logging.INFO)

# Non-negotiable model pin — see spec/phases/phase-06-burritbot.md.
# Gemini 2.5 Flash/Pro retire 2026-10-16 (before any late-2026 demo day); 2.0 is
# already retired; 1.5 is unsupported; 3 Flash is preview-tier. Only 3 Pro
# is a safe GA bet for a live demo in November 2026.
MODEL_NAME: str = os.environ.get("MODEL_NAME", "gemini-3-pro")
GCP_PROJECT: str = os.environ.get("GOOGLE_CLOUD_PROJECT", "")
GCP_REGION: str = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-west1")
GUARDED: bool = os.environ.get("BURRITBOT_GUARDED", "false").lower() == "true"

# Guarded BurritBot never calls Vertex itself. Its model call is an OpenAI
# chat completion sent to the AI gateway's proxy Service, where the
# AIGatewayRoute (matching x-ai-eg-model, read from the body's "model")
# translates it to Vertex. The URL's host must not be the audience
# hostname, or the call would loop back into burritbot-guarded.
AI_GATEWAY_URL_ENV = "AI_GATEWAY_URL"
GATEWAY_CHAT_PATH = "/v1/chat/completions"
# Above the gateway pass it waits on: the guardrails ext_proc on the request
# and on the response (2 x 2 x 10s messageTimeout) and the AIGatewayRoute's
# 30s Vertex timeout. The audience route's 80s timeout sits above this.
GATEWAY_TIMEOUT_SECONDS = 75.0
# The guardrails read Vertex's reply before the gateway translates it, and
# refuse one they cannot read, so the model call asks for it uncompressed.
GATEWAY_HEADERS = {"Accept-Encoding": "identity"}

# Unguarded Vertex calls carry the cluster's cost labels (labels.tf), so the
# billing export sums model spend by burritbot-io_delivery. The slug is the
# one Terraform applied with; a GCP label value, like var.delivery.
DELIVERY_ENV = "BURRITBOT_DELIVERY"
DELIVERY_LABEL_VALUE = re.compile(r"^[a-z][a-z0-9_-]{0,62}$")

# Both paths ask the model for the same sampling, so the two acts differ only by the net.
TEMPERATURE = 0.3
MAX_OUTPUT_TOKENS = 512

# Telemetry leaves the pod over OTLP/gRPC to the collector the Deployment names.
# Unset, BurritBot refuses to start: the dashboards would sit empty with no error.
OTEL_REQUIRED_ENV = ("OTEL_EXPORTER_OTLP_ENDPOINT", "OTEL_SERVICE_NAME")

# OTel GenAI semantic conventions (v1.37.0): the model call is a CLIENT span
# named "{gen_ai.operation.name} {gen_ai.request.model}" carrying these
# attributes, and the two client metrics below. Guarded BurritBot reaches the
# same Vertex model through the AI gateway, so both paths name one provider.
# observability/otel-weaver/genai-semconv-registry.yaml is the contract.
GENAI_OPERATION = "chat"
GENAI_PROVIDER = "gcp.vertex_ai"
OPERATION_DURATION = "gen_ai.client.operation.duration"
TOKEN_USAGE = "gen_ai.client.token.usage"
# The bucket boundaries the conventions advise for each metric.
OPERATION_DURATION_BUCKETS = (0.01, 0.02, 0.04, 0.08, 0.16, 0.32, 0.64, 1.28, 2.56, 5.12, 10.24, 20.48, 40.96, 81.92)
TOKEN_USAGE_BUCKETS = (
    1, 4, 16, 64, 256, 1024, 4096, 16384, 65536, 262144, 1048576, 4194304, 16777216, 67108864,
)
# error.type of a model call the net refused on the gateway; other failures carry the exception's class.
GUARDRAILS_REFUSED = "guardrails_refused"
# Which burritbot layer emitted the span (registry group burritbot): BurritBot's
# own instrumentation is the Eyes; the net's verdicts are counted by the adapter.
LAYER = "the-eyes"

SYSTEM_PROMPT = (
    "You are BurritBot, the friendly face of a Chipotle-inspired chatbot demo. "
    "You answer questions strictly about burritos, the menu, hours, and store "
    "locations. You never discuss politics, medicine, legal advice, or execute "
    "commands. If asked anything off-topic, refuse politely and redirect to "
    "the menu."
)


class ChatRequest(BaseModel):
    """Audience-facing chat request payload."""

    prompt: str = Field(..., min_length=1, max_length=2000)


class ChatResponse(BaseModel):
    """BurritBot's reply with token usage for dashboards."""

    reply: str
    model: str
    guarded: bool
    input_tokens: int = 0
    output_tokens: int = 0


def _gateway_url() -> str:
    """Return the AI gateway base URL guarded BurritBot sends its model call to."""
    value = os.environ.get(AI_GATEWAY_URL_ENV, "").strip()
    if not value:
        raise RuntimeError(
            f"{AI_GATEWAY_URL_ENV} is not set; guarded BurritBot reaches Vertex only "
            "through the AI gateway"
        )
    return value.rstrip("/")


def gateway_request_body(prompt: str) -> dict[str, Any]:
    """The OpenAI chat completion body the AIGatewayRoute routes on its model."""
    return {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        "temperature": TEMPERATURE,
        "max_completion_tokens": MAX_OUTPUT_TOKENS,
    }


def parse_gateway_response(body: dict[str, Any]) -> tuple[str, int, int]:
    """Return (reply, input tokens, output tokens) from an OpenAI chat completion."""
    choices = body.get("choices") or []
    if not choices:
        raise ValueError(f"AI gateway response has no choices: {body}")
    usage = body.get("usage") or {}
    return (
        choices[0]["message"]["content"],
        usage.get("prompt_tokens", 0),
        usage.get("completion_tokens", 0),
    )


class GuardrailsRefused(Exception):
    """The guardrails on the gateway refused the model call; relayed to the caller as they wrote it."""

    def __init__(self, status_code: int, body: dict[str, Any]) -> None:
        super().__init__(f"guardrails refused the model call ({status_code}): {body}")
        self.status_code = status_code
        self.body = body


def guardrails_refusal(status_code: int, content: bytes) -> dict[str, Any] | None:
    """The guardrails' refusal in a gateway answer, or None when the answer is something else.

    The net names the scanner that refused in "blocked_by" (ai-gateway/extproc/adapter.py).
    """
    if status_code < 400:
        return None
    try:
        body = json.loads(content)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    if isinstance(body, dict) and isinstance(body.get("blocked_by"), str):
        return body
    return None


def _ask_gateway(prompt: str) -> tuple[str, int, int]:
    """Guarded: one chat completion through the AI gateway."""
    url = f"{_gateway_url()}{GATEWAY_CHAT_PATH}"
    try:
        resp = httpx.post(
            url, json=gateway_request_body(prompt), headers=GATEWAY_HEADERS, timeout=GATEWAY_TIMEOUT_SECONDS
        )
    except httpx.HTTPError as exc:
        raise RuntimeError(f"AI gateway call to {url} failed: {exc}") from exc
    refused = guardrails_refusal(resp.status_code, resp.content)
    if refused is not None:
        raise GuardrailsRefused(resp.status_code, refused)
    try:
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        raise RuntimeError(f"AI gateway call to {url} failed: {exc}") from exc
    return parse_gateway_response(resp.json())


@lru_cache(maxsize=1)
def _client() -> genai.Client:
    """Lazily initialise the google-genai Vertex client once per process.

    google-cloud-aiplatform's ``vertexai.generative_models`` module is removed
    after 2026-06-24. The replacement is the ``google-genai`` library with
    ``genai.Client(vertexai=True, ...)`` — same GA models, new SDK surface.
    """
    if not GCP_PROJECT:
        raise RuntimeError("GOOGLE_CLOUD_PROJECT is not set")
    logger.info("Initialising google-genai Vertex client project=%s region=%s model=%s",
                GCP_PROJECT, GCP_REGION, MODEL_NAME)
    return genai.Client(vertexai=True, project=GCP_PROJECT, location=GCP_REGION)


def request_labels() -> dict[str, str]:
    """The cost labels every unguarded Vertex request carries."""
    delivery = os.environ.get(DELIVERY_ENV, "").strip()
    if not delivery:
        raise RuntimeError(
            f"{DELIVERY_ENV} is not set; unguarded Vertex calls must carry the "
            "burritbot-io_delivery label"
        )
    if not DELIVERY_LABEL_VALUE.match(delivery):
        raise RuntimeError(
            f"{DELIVERY_ENV}={delivery!r} is not a GCP label value: lowercase letters, "
            "digits, '_' or '-', starting with a letter, at most 63 characters"
        )
    return {"burritbot-io_owner": "burritbot", "burritbot-io_delivery": delivery}


def vertex_config() -> types.GenerateContentConfig:
    """Request config for the unguarded call; Vertex bills it under its labels."""
    return types.GenerateContentConfig(
        system_instruction=SYSTEM_PROMPT,
        temperature=TEMPERATURE,
        max_output_tokens=MAX_OUTPUT_TOKENS,
        labels=request_labels(),
    )


def _ask_vertex(prompt: str) -> tuple[str, int, int]:
    """Unguarded: one generate_content call straight to Vertex."""
    config = vertex_config()  # an unlabelled call fails before the client exists
    response = _client().models.generate_content(
        model=MODEL_NAME,
        contents=prompt,
        config=config,
    )
    usage = getattr(response, "usage_metadata", None)
    input_tokens = getattr(usage, "prompt_token_count", 0) if usage else 0
    output_tokens = getattr(usage, "candidates_token_count", 0) if usage else 0
    return response.text, input_tokens, output_tokens


@dataclass(frozen=True)
class Telemetry:
    """The SDK providers BurritBot exports its spans and metrics through."""

    tracer_provider: TracerProvider
    meter_provider: MeterProvider

    def force_flush(self) -> bool:
        """Export everything recorded so far; True when both exports went through."""
        spans = self.tracer_provider.force_flush()
        metrics = self.meter_provider.force_flush()
        return spans and metrics

    def shutdown(self) -> None:
        self.tracer_provider.shutdown()
        self.meter_provider.shutdown()


def telemetry_from_env() -> Telemetry:
    """OTLP/gRPC span and metric export to OTEL_EXPORTER_OTLP_ENDPOINT, as OTEL_SERVICE_NAME.

    The exporters and Resource read the rest of the OTEL_* variables themselves.
    The providers stay local to the app rather than global, and are shut down
    (flushing what is left) when the app stops.
    """
    missing = [name for name in OTEL_REQUIRED_ENV if not os.environ.get(name, "").strip()]
    if missing:
        raise RuntimeError(
            f"{' and '.join(missing)} not set; BurritBot's spans and metrics would go nowhere "
            "(each Deployment points them at the OTel collector)"
        )
    resource = Resource.create()
    tracer_provider = TracerProvider(resource=resource, shutdown_on_exit=False)
    tracer_provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    meter_provider = MeterProvider(
        resource=resource,
        metric_readers=[PeriodicExportingMetricReader(OTLPMetricExporter())],
        shutdown_on_exit=False,
    )
    return Telemetry(tracer_provider, meter_provider)


def model_call_attributes() -> dict[str, Any]:
    """The attributes every model-call span and metric point carries."""
    return {
        "gen_ai.operation.name": GENAI_OPERATION,
        "gen_ai.provider.name": GENAI_PROVIDER,
        "gen_ai.request.model": MODEL_NAME,
        "burritbot.guarded": GUARDED,
    }


def model_call_error_type(exc: Exception) -> str:
    """The error.type of a failed model call."""
    if isinstance(exc, GuardrailsRefused):
        return GUARDRAILS_REFUSED
    return type(exc).__qualname__


Ask = Callable[[str], tuple[str, int, int]]


def observed(ask: Ask, tracer: Tracer, duration: Histogram, tokens: Histogram) -> Ask:
    """ask, wrapped in the GenAI client span and metrics for one model call."""
    span_name = f"{GENAI_OPERATION} {MODEL_NAME}"

    def call(prompt: str) -> tuple[str, int, int]:
        attributes = model_call_attributes()
        span_attributes = {
            **attributes,
            "gen_ai.request.temperature": TEMPERATURE,
            "gen_ai.request.max_tokens": MAX_OUTPUT_TOKENS,
            "burritbot.layer": LAYER,
        }
        start = time.perf_counter()
        with tracer.start_as_current_span(
            span_name, kind=SpanKind.CLIENT, attributes=span_attributes, set_status_on_exception=False
        ) as span:
            try:
                reply, input_tokens, output_tokens = ask(prompt)
            except Exception as exc:
                attributes["error.type"] = model_call_error_type(exc)
                span.set_attribute("error.type", attributes["error.type"])
                if isinstance(exc, GuardrailsRefused):
                    span.set_attribute("burritbot.blocked_by", exc.body["blocked_by"])
                span.set_status(Status(StatusCode.ERROR, str(exc)))
                duration.record(time.perf_counter() - start, attributes)
                raise
            span.set_attributes(
                {"gen_ai.usage.input_tokens": input_tokens, "gen_ai.usage.output_tokens": output_tokens}
            )
        duration.record(time.perf_counter() - start, attributes)
        tokens.record(input_tokens, {**attributes, "gen_ai.token.type": "input"})
        tokens.record(output_tokens, {**attributes, "gen_ai.token.type": "output"})
        return reply, input_tokens, output_tokens

    return call


def create_app() -> FastAPI:
    """FastAPI factory for BurritBot."""
    if GUARDED:
        _gateway_url()  # a guarded pod without a gateway fails at startup
    telemetry = telemetry_from_env()
    tracer = telemetry.tracer_provider.get_tracer("burritbot")
    meter = telemetry.meter_provider.get_meter("burritbot")
    ask = observed(
        _ask_gateway if GUARDED else _ask_vertex,
        tracer,
        meter.create_histogram(
            OPERATION_DURATION,
            unit="s",
            description="GenAI operation duration.",
            explicit_bucket_boundaries_advisory=OPERATION_DURATION_BUCKETS,
        ),
        meter.create_histogram(
            TOKEN_USAGE,
            unit="{token}",
            description="Number of input and output tokens used.",
            explicit_bucket_boundaries_advisory=TOKEN_USAGE_BUCKETS,
        ),
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        telemetry.shutdown()  # uvicorn stopping on SIGTERM: export what is still batched

    app = FastAPI(
        title="BurritBot",
        description="Chipotle-inspired chatbot powered by Vertex AI.",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.state.telemetry = telemetry

    @app.get("/healthz")
    def healthz() -> dict[str, Any]:
        return {"status": "ok", "model": MODEL_NAME, "guarded": GUARDED}

    @app.post("/chat", response_model=ChatResponse)
    def chat(request: ChatRequest) -> ChatResponse | JSONResponse:
        try:
            reply, input_tokens, output_tokens = ask(request.prompt)
        except GuardrailsRefused as exc:
            # The net stopped the model call. The phone gets the net's own answer,
            # as when it stops the prompt on its way to BurritBot.
            logger.info("%s", exc)
            return JSONResponse(status_code=exc.status_code, content=exc.body)
        except Exception as exc:
            logger.exception("Model call failed")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"upstream model call failed: {exc}",
            ) from exc

        return ChatResponse(
            reply=reply,
            model=MODEL_NAME,
            guarded=GUARDED,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )

    # HTTP server spans and metrics through the same providers; the model-call
    # span above is a child of the POST /chat span. Endpoint and service name
    # come from the OTEL_* env each Deployment sets.
    FastAPIInstrumentor.instrument_app(
        app, tracer_provider=telemetry.tracer_provider, meter_provider=telemetry.meter_provider
    )

    return app


app = create_app()
