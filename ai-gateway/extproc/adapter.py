# ABOUTME: Envoy ext_proc adapter: turns ProcessingRequest bodies into calls to a guardrails scanner's REST API.
# ABOUTME: Runs as the burritbot-extproc sidecar beside NeMo Guardrails or LLM Guard; blocks, rewrites or fails closed.

from __future__ import annotations

import asyncio
import json
import logging
import os
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

import httpx
from envoy_data_plane.envoy.config.core.v3 import (
    HeaderValue,
    HeaderValueOption,
    HeaderValueOptionHeaderAppendAction,
)
from envoy_data_plane.envoy.service.ext_proc.v3 import (
    BodyMutation,
    BodyResponse,
    CommonResponse,
    ExternalProcessorBase,
    HeaderMutation,
    HeadersResponse,
    HttpHeaders,
    ImmediateResponse,
    ProcessingRequest,
    ProcessingResponse,
    TrailersResponse,
)
from envoy_data_plane.envoy.type.v3 import HttpStatus, StatusCode
from grpclib.server import Server
from grpclib.utils import graceful_exit


logger = logging.getLogger("burritbot-extproc")

# A path into a JSON document: object keys and list indexes.
Path = tuple[str | int, ...]

NEMO = "nemo-guardrails"
LLM_GUARD = "llm-guard"


class UnreadableBody(ValueError):
    """A request body the adapter cannot find user text in. Refused, never forwarded unscanned."""


class ScannerError(RuntimeError):
    """The scanner could not give a verdict: unreachable, an error status, or a reply out of contract."""


@dataclass(frozen=True)
class Verdict:
    """One scanner's answer for one text."""

    allowed: bool
    # The text to forward. Differs from the scanned text when the scanner sanitized it.
    text: str
    # The scanner's per-check results, returned in the block body and logged.
    findings: dict[str, Any]


# --- where the text lives in the bodies on the guarded path ----------------


def _texts_in_content(content: object, path: Path) -> list[tuple[Path, str]]:
    """Text in an OpenAI message content: a string, or a list of typed parts."""
    if isinstance(content, str):
        return [(path, content)]
    if isinstance(content, list):
        return [
            (path + (i, "text"), part["text"])
            for i, part in enumerate(content)
            if isinstance(part, dict) and part.get("type") == "text" and isinstance(part.get("text"), str)
        ]
    return []


def prompt_texts(body: bytes) -> list[tuple[Path, str]]:
    """The user text in a request body: BurritBot's {"prompt"} or OpenAI chat {"messages"}.

    Raises UnreadableBody when there is none: the net does not let text it
    could not read reach the model.
    """
    try:
        doc = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise UnreadableBody(f"request body is not JSON: {exc}") from exc
    found: list[tuple[Path, str]] = []
    if isinstance(doc, dict):
        if isinstance(doc.get("prompt"), str):
            found.append((("prompt",), doc["prompt"]))
        for i, message in enumerate(doc.get("messages") or []):
            if isinstance(message, dict) and message.get("role") == "user":
                found += _texts_in_content(message.get("content"), ("messages", i, "content"))
    if not found:
        raise UnreadableBody("request body carries no prompt and no user message")
    return found


def _texts_in_candidate(candidate: object, path: Path) -> list[tuple[Path, str]]:
    """Text in a Vertex generateContent candidate: the text of each content part."""
    if not (isinstance(candidate, dict) and isinstance(candidate.get("content"), dict)):
        return []
    return [
        (path + ("content", "parts", j, "text"), part["text"])
        for j, part in enumerate(candidate["content"].get("parts") or [])
        if isinstance(part, dict) and isinstance(part.get("text"), str)
    ]


def output_texts(body: bytes) -> list[tuple[Path, str]]:
    """The model text in a response body: BurritBot's {"reply"}, Vertex's {"candidates"} or OpenAI {"choices"}.

    On the model hop the net sees Vertex's own reply: the AI Gateway's ext_proc
    translates it to OpenAI only after this one (see lost_rewrites). Empty for
    bodies that carry no model output (health checks, error details, a refusal
    BurritBot relays).
    """
    try:
        doc = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return []
    found: list[tuple[Path, str]] = []
    if isinstance(doc, dict):
        if isinstance(doc.get("reply"), str):
            found.append((("reply",), doc["reply"]))
        for i, candidate in enumerate(doc.get("candidates") or []):
            found += _texts_in_candidate(candidate, ("candidates", i))
        for i, choice in enumerate(doc.get("choices") or []):
            if isinstance(choice, dict) and isinstance(choice.get("message"), dict):
                found += _texts_in_content(choice["message"].get("content"), ("choices", i, "message", "content"))
    return found


def lost_rewrites(replacements: list[tuple[Path, str]]) -> list[Path]:
    """Request rewrites that would never reach the model: those inside an OpenAI chat body.

    That body is guarded BurritBot's model call. The AI Gateway inserts its own
    ext_proc ahead of every other one on the listener and translates for Vertex
    the request body it read there, not the body this adapter hands back
    (insertAIGatewayExtProcFilter and originalRequestBodyRaw, v0.6.0 to v1.2.0).
    """
    return [path for path, _ in replacements if path[0] == "messages"]


def replace_texts(body: bytes, replacements: list[tuple[Path, str]]) -> bytes:
    """The body with the text at each path replaced."""
    doc = json.loads(body)
    for path, text in replacements:
        node = doc
        for key in path[:-1]:
            node = node[key]
        node[path[-1]] = text
    return json.dumps(doc, ensure_ascii=False).encode("utf-8")


# --- the scanners' REST contracts ------------------------------------------


def llm_guard_verdict(reply: object, text_key: str) -> Verdict:
    """Read an llm-guard-api /analyze/prompt or /analyze/output reply.

    {"is_valid": bool, "scanners": {name: score}, "sanitized_prompt"|"sanitized_output": str}
    """
    if not (
        isinstance(reply, dict)
        and isinstance(reply.get("is_valid"), bool)
        and isinstance(reply.get("scanners"), dict)
        and isinstance(reply.get(text_key), str)
    ):
        raise ScannerError(f"llm-guard reply lacks is_valid, scanners or {text_key}: {reply!r}")
    return Verdict(allowed=reply["is_valid"], text=reply[text_key], findings=reply["scanners"])


def nemo_checks_payload(model: str, config_id: str, prompt: str, output: str | None = None) -> dict[str, Any]:
    """The NeMo Guardrails microservice /v1/guardrail/checks body for one exchange."""
    messages = [{"role": "user", "content": prompt}]
    if output is not None:
        messages.append({"role": "assistant", "content": output})
    return {"model": model, "messages": messages, "guardrails": {"config_id": config_id}}


def nemo_verdict(reply: object, text: str) -> Verdict:
    """Read a /v1/guardrail/checks reply: {"status": "success"|"blocked", "rails_status": {...}}.

    The checks endpoint judges; it does not rewrite, so the text passes as scanned.
    """
    if not (
        isinstance(reply, dict)
        and reply.get("status") in ("success", "blocked")
        and isinstance(reply.get("rails_status"), dict)
    ):
        raise ScannerError(f"nemo-guardrails reply lacks a success/blocked status or rails_status: {reply!r}")
    return Verdict(allowed=reply["status"] == "success", text=text, findings=reply["rails_status"])


class Scanner:
    """A guardrails service reached over its REST API."""

    name: str

    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    async def _post(self, path: str, payload: dict[str, Any]) -> object:
        try:
            resp = await self._client.post(path, json=payload)
        except httpx.HTTPError as exc:
            raise ScannerError(f"{self.name} {path} unreachable: {exc!r}") from exc
        if resp.status_code != 200:
            raise ScannerError(f"{self.name} {path} answered {resp.status_code}: {resp.text[:500]}")
        try:
            return resp.json()
        except json.JSONDecodeError as exc:
            raise ScannerError(f"{self.name} {path} answered non-JSON: {resp.text[:500]}") from exc

    async def check_prompt(self, prompt: str) -> Verdict:
        raise NotImplementedError

    async def check_output(self, prompt: str, output: str) -> Verdict:
        raise NotImplementedError


class LlmGuard(Scanner):
    name = LLM_GUARD

    async def check_prompt(self, prompt: str) -> Verdict:
        reply = await self._post("/analyze/prompt", {"prompt": prompt})
        return llm_guard_verdict(reply, "sanitized_prompt")

    async def check_output(self, prompt: str, output: str) -> Verdict:
        reply = await self._post("/analyze/output", {"prompt": prompt, "output": output})
        return llm_guard_verdict(reply, "sanitized_output")


class NemoGuardrails(Scanner):
    name = NEMO

    def __init__(self, client: httpx.AsyncClient, model: str, config_id: str) -> None:
        super().__init__(client)
        self._model = model
        self._config_id = config_id

    async def check_prompt(self, prompt: str) -> Verdict:
        reply = await self._post("/v1/guardrail/checks", nemo_checks_payload(self._model, self._config_id, prompt))
        return nemo_verdict(reply, prompt)

    async def check_output(self, prompt: str, output: str) -> Verdict:
        payload = nemo_checks_payload(self._model, self._config_id, prompt, output)
        reply = await self._post("/v1/guardrail/checks", payload)
        return nemo_verdict(reply, output)


# --- ext_proc responses ----------------------------------------------------


def _overwrite(key: str, value: str) -> HeaderValueOption:
    return HeaderValueOption(
        header=HeaderValue(key=key, raw_value=value.encode("utf-8")),
        append_action=HeaderValueOptionHeaderAppendAction.OVERWRITE_IF_EXISTS_OR_ADD,
    )


def refusal(code: StatusCode, detail: str, **extra: Any) -> ProcessingResponse:
    """Stop the exchange and answer the client directly with a JSON body."""
    return ProcessingResponse(
        immediate_response=ImmediateResponse(
            status=HttpStatus(code=code),
            headers=HeaderMutation(set_headers=[_overwrite("content-type", "application/json")]),
            body=json.dumps({"detail": detail, **extra}).encode("utf-8"),
            details=f"burritbot_extproc_{code.name.lower()}",
        )
    )


def body_passes(request: bool, new_body: bytes | None = None) -> ProcessingResponse:
    """Let the body through, replaced by new_body (with its content-length) when given."""
    common = CommonResponse()
    if new_body is not None:
        common = CommonResponse(
            header_mutation=HeaderMutation(set_headers=[_overwrite("content-length", str(len(new_body)))]),
            body_mutation=BodyMutation(body=new_body),
        )
    if request:
        return ProcessingResponse(request_body=BodyResponse(response=common))
    return ProcessingResponse(response_body=BodyResponse(response=common))


def scanned_body(scanner: str, request: bool, body: bytes, replacements: list[tuple[Path, str]]) -> ProcessingResponse:
    """The body a scanner allowed: as it came, rewritten, or refused when the rewrite would be dropped."""
    if not replacements:
        return body_passes(request)
    if request and lost_rewrites(replacements):
        logger.warning("%s sanitized a model-hop prompt the gateway would send unsanitized; refusing", scanner)
        return refusal(
            StatusCode.Forbidden,
            "BurritBot's guardrails had to change this prompt, and the AI gateway would send it to the model "
            "unchanged; nothing was let through.",
            blocked_by=scanner,
            direction="prompt",
        )
    logger.info("%s sanitized %d field(s) of the %s", scanner, len(replacements), "prompt" if request else "reply")
    return body_passes(request, replace_texts(body, replacements))


def content_encoding(headers: HttpHeaders) -> str:
    """The content-encoding a header block declares, lower-cased; empty when it declares none."""
    for header in headers.headers.headers if headers.headers else []:
        if header.key.lower() == "content-encoding":
            value = header.raw_value.decode("utf-8", "replace") if header.raw_value else header.value
            return value.strip().lower()
    return ""


# --- the processor ---------------------------------------------------------


class GuardrailsProcessor(ExternalProcessorBase):
    """One ext_proc stream per HTTP exchange: scan the prompt, then the reply to it."""

    def __init__(self, scanner: Scanner) -> None:
        self.scanner = scanner

    async def check_request(self, body: bytes) -> tuple[ProcessingResponse, str]:
        """The response to a buffered request body, and the prompt kept for the output check."""
        try:
            texts = prompt_texts(body)
        except UnreadableBody as exc:
            logger.warning("refused unreadable request body: %s", exc)
            return refusal(StatusCode.BadRequest, f"BurritBot's guardrails could not read this request: {exc}"), ""
        return await self._judge(texts, body, request=True, prompt="\n".join(t for _, t in texts))

    async def check_response(self, body: bytes, prompt: str, encoding: str = "") -> ProcessingResponse:
        if body and encoding not in ("", "identity"):
            # Guarded BurritBot asks the gateway for identity, so only a reply nobody
            # asked for arrives compressed. Its text cannot be read, so it is refused.
            logger.error("%s cannot read a %s-encoded reply; refusing", self.scanner.name, encoding)
            return refusal(
                StatusCode.BadGateway,
                f"BurritBot's guardrails could not read a {encoding}-encoded reply; nothing was let through.",
                blocked_by=self.scanner.name,
            )
        texts = output_texts(body)
        if not texts:
            return body_passes(request=False)
        response, _ = await self._judge(texts, body, request=False, prompt=prompt)
        return response

    async def _judge(
        self, texts: list[tuple[Path, str]], body: bytes, *, request: bool, prompt: str
    ) -> tuple[ProcessingResponse, str]:
        direction = "prompt" if request else "reply"
        replacements: list[tuple[Path, str]] = []
        for path, text in texts:
            try:
                if request:
                    verdict = await self.scanner.check_prompt(text)
                else:
                    verdict = await self.scanner.check_output(prompt, text)
            except ScannerError as exc:
                logger.error("%s check of the %s failed; refusing: %s", self.scanner.name, direction, exc)
                return refusal(
                    StatusCode.ServiceUnavailable,
                    f"BurritBot's guardrails are unavailable ({self.scanner.name}); nothing was let through.",
                    blocked_by=self.scanner.name,
                ), prompt
            if not verdict.allowed:
                logger.info("%s blocked the %s: %s", self.scanner.name, direction, verdict.findings)
                return refusal(
                    StatusCode.Forbidden,
                    f"BurritBot's guardrails stopped this {direction}. BurritBot only talks burritos.",
                    blocked_by=self.scanner.name,
                    direction=direction,
                    findings=verdict.findings,
                ), prompt
            if verdict.text != text:
                replacements.append((path, verdict.text))
        return scanned_body(self.scanner.name, request, body, replacements), prompt

    async def process(self, messages: AsyncIterator[ProcessingRequest]) -> AsyncIterator[ProcessingResponse]:
        prompt = ""
        encoding = ""
        async for req in messages:
            if req.request_headers is not None:
                yield ProcessingResponse(request_headers=HeadersResponse())
            elif req.request_body is not None:
                response, prompt = await self.check_request(req.request_body.body)
                yield response
            elif req.response_headers is not None:
                encoding = content_encoding(req.response_headers)
                yield ProcessingResponse(response_headers=HeadersResponse())
            elif req.response_body is not None:
                yield await self.check_response(req.response_body.body, prompt, encoding)
            elif req.request_trailers is not None:
                yield ProcessingResponse(request_trailers=TrailersResponse())
            elif req.response_trailers is not None:
                yield ProcessingResponse(response_trailers=TrailersResponse())
            else:
                raise ValueError(f"ProcessingRequest carries no phase this adapter handles: {req!r}")


# --- configuration and entry point -----------------------------------------


def _require_env(name: str) -> str:
    value = os.environ.get(name, "")
    if not value:
        raise RuntimeError(f"{name} is not set")
    return value


@dataclass(frozen=True)
class Config:
    scanner: str
    scanner_url: str
    timeout_seconds: float
    port: int
    nemo_model: str = ""
    nemo_config_id: str = ""

    @classmethod
    def from_env(cls) -> Config:
        scanner = _require_env("SCANNER")
        if scanner not in (NEMO, LLM_GUARD):
            raise RuntimeError(f"SCANNER must be {NEMO} or {LLM_GUARD}, got {scanner!r}")
        nemo = scanner == NEMO
        return cls(
            scanner=scanner,
            scanner_url=_require_env("SCANNER_URL"),
            timeout_seconds=float(_require_env("SCANNER_TIMEOUT_SECONDS")),
            port=int(_require_env("EXTPROC_PORT")),
            nemo_model=_require_env("NEMO_GUARDRAILS_MODEL") if nemo else "",
            nemo_config_id=_require_env("NEMO_GUARDRAILS_CONFIG_ID") if nemo else "",
        )

    def scanner_for(self, client: httpx.AsyncClient) -> Scanner:
        if self.scanner == NEMO:
            return NemoGuardrails(client, self.nemo_model, self.nemo_config_id)
        return LlmGuard(client)

    def http_client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(base_url=self.scanner_url, timeout=self.timeout_seconds)


async def serve(config: Config, host: str = "0.0.0.0") -> None:
    async with config.http_client() as client:
        server = Server([GuardrailsProcessor(config.scanner_for(client))])
        with graceful_exit([server]):
            await server.start(host, config.port)
            logger.info("ext_proc adapter for %s at %s listening on %d", config.scanner, config.scanner_url, config.port)
            await server.wait_closed()


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    asyncio.run(serve(Config.from_env()))


if __name__ == "__main__":
    main()
