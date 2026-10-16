# ABOUTME: The nemo-guardrails Deployment against the NeMo Guardrails microservice 25.07 image (#90):
# ABOUTME: listen port, config store layout and health path match NVIDIA's 25.07 docs and the ext_proc adapter.

from __future__ import annotations

import copy
import inspect
import json
import urllib.request
from collections.abc import Callable, Iterator

import pytest
import yaml

from conftest import PROJECT_ROOT
from helpers.kubectl_helpers import port_forward


def _load_adapter():
    import importlib.util
    import sys

    name = "burritbot_extproc_adapter"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, PROJECT_ROOT / "ai-gateway" / "extproc" / "adapter.py")
    module = importlib.util.module_from_spec(spec)
    # dataclasses resolve string annotations through sys.modules.
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


adapter = _load_adapter()

DEPLOYMENT = PROJECT_ROOT / "ai-gateway" / "nemo-guardrails" / "deployment.yaml"
NAMESPACE = "burritbot-net"
SCANNER = "nemo-guardrails"
SIDECAR = "burritbot-extproc"
IMAGE = "nvcr.io/nvidia/nemo-microservices/guardrails:25.07"
CONFIG_CONFIGMAP = "nemo-guardrails-config"
RAILS_CONFIGMAP = "nemo-guardrails-rails"

# The 25.07 microservice, from NVIDIA's 25.7.0 docs
# (archive.docs.nvidia.com/nemo/microservices/25.7.0/):
# - guardrails/reference.html: GUARDRAILS_PORT defaults to 7331; CONFIG_STORE_PATH
#   (default /app/services/guardrails/config-store) is the local config store;
#   DEFAULT_CONFIG_ID (default "default") serves requests that name no config.
# - guardrails/manage-guardrail-configs/configuration-store.html: one directory per
#   config id under the store, each holding config.yml and rails/.
# - _static/.../openapi/individual/guardrails.openapi.yaml: the paths below.
MICROSERVICE_DEFAULT_PORT = 7331
API_PATHS = frozenset(
    {
        "/v1/guardrail/chat/completions",
        "/v1/guardrail/checks",
        "/v1/guardrail/completions",
        "/v1/guardrail/configs",
        "/v1/guardrail/configs/{namespace}/{config_name}",
        "/v1/guardrail/models",
        "/v1/guardrail/models/{model_id}",
        "/v1/health",
    }
)
HEALTH_PATH = "/v1/health"
CHECKS_PATH = "/v1/guardrail/checks"


def _docs() -> list[dict]:
    with DEPLOYMENT.open(encoding="utf-8") as fp:
        return [d for d in yaml.safe_load_all(fp) if d]


def _deployment(docs: list[dict]) -> dict:
    return next(d for d in docs if d["kind"] == "Deployment")


def _service(docs: list[dict]) -> dict:
    return next(d for d in docs if d["kind"] == "Service")


def _container(deploy: dict, name: str) -> dict:
    return next(c for c in deploy["spec"]["template"]["spec"]["containers"] if c["name"] == name)


def _env(container: dict) -> dict[str, str]:
    return {e["name"]: e["value"] for e in container.get("env") or []}


def microservice_violations(deploy: dict) -> list[str]:
    """Where the Deployment disagrees with the 25.07 microservice or with the adapter in front of it."""
    out: list[str] = []
    scanner = _container(deploy, SCANNER)
    env = _env(scanner)
    adapter_env = _env(_container(deploy, SIDECAR))

    if scanner["image"] != IMAGE:
        out.append(f"{SCANNER} runs {scanner['image']!r}; these checks hold for {IMAGE}")

    # Port: the microservice listens on GUARDRAILS_PORT, 7331 unless set.
    port = int(env.get("GUARDRAILS_PORT", MICROSERVICE_DEFAULT_PORT))
    http = [p for p in scanner.get("ports") or [] if p.get("name") == "http"]
    if [p["containerPort"] for p in http] != [port]:
        out.append(f"{SCANNER} listens on GUARDRAILS_PORT {port}, its http containerPort is {[p['containerPort'] for p in http]}")
    if adapter_env.get("SCANNER_URL") != f"http://127.0.0.1:{port}":
        out.append(f"the adapter's SCANNER_URL {adapter_env.get('SCANNER_URL')!r} is not the microservice's port {port}")

    # Config store: the adapter's config id must name a directory in CONFIG_STORE_PATH.
    if "NEMO_GUARDRAILS_CONFIG_PATH" in env:
        out.append("NEMO_GUARDRAILS_CONFIG_PATH is the open-source server's variable; the microservice reads CONFIG_STORE_PATH")
    store = env.get("CONFIG_STORE_PATH")
    config_id = adapter_env.get("NEMO_GUARDRAILS_CONFIG_ID")
    if not store:
        out.append("CONFIG_STORE_PATH is unset; the image's built-in store has no burritbot config")
    if env.get("DEFAULT_CONFIG_ID") != config_id:
        out.append(f"DEFAULT_CONFIG_ID {env.get('DEFAULT_CONFIG_ID')!r} is not the adapter's config id {config_id!r}")
    if store and config_id:
        volumes = {
            v["name"]: v["configMap"]["name"]
            for v in deploy["spec"]["template"]["spec"].get("volumes") or []
            if "configMap" in v
        }
        mounts = {
            (volumes.get(m["name"]), m["mountPath"], m.get("subPath"))
            for m in scanner.get("volumeMounts") or []
        }
        config_dir = f"{store.rstrip('/')}/{config_id}"
        if (CONFIG_CONFIGMAP, f"{config_dir}/config.yml", "config.yaml") not in mounts:
            out.append(f"{CONFIG_CONFIGMAP} is not mounted at {config_dir}/config.yml, where config id {config_id!r} resolves")
        if (RAILS_CONFIGMAP, f"{config_dir}/rails", None) not in mounts:
            out.append(f"{RAILS_CONFIGMAP} is not mounted at {config_dir}/rails, beside config id {config_id!r}'s config.yml")

    # Probes: the microservice's health path, on the port it serves.
    for probe in ("readinessProbe", "livenessProbe"):
        get = (scanner.get(probe) or {}).get("httpGet") or {}
        if get.get("path") != HEALTH_PATH:
            out.append(f"{SCANNER} {probe} asks {get.get('path')!r}; the 25.07 API serves health at {HEALTH_PATH}")
        if get.get("port") not in ("http", port):
            out.append(f"{SCANNER} {probe} probes port {get.get('port')!r}, not the microservice's {port}")
    return out


@pytest.mark.static
def test_deployment_matches_the_25_07_microservice() -> None:
    violations = microservice_violations(_deployment(_docs()))
    assert not violations, "nemo-guardrails disagrees with guardrails:25.07:\n  " + "\n  ".join(violations)


@pytest.mark.static
def test_adapter_and_probe_paths_are_25_07_api_paths() -> None:
    assert CHECKS_PATH in API_PATHS and HEALTH_PATH in API_PATHS
    source = inspect.getsource(adapter.NemoGuardrails)
    assert f'"{CHECKS_PATH}"' in source, "the adapter no longer posts to the 25.07 checks path"


@pytest.mark.static
def test_service_http_port_is_the_microservice_port() -> None:
    docs = _docs()
    env = _env(_container(_deployment(docs), SCANNER))
    http = next(p for p in _service(docs)["spec"]["ports"] if p["name"] == "http")
    assert http["port"] == int(env["GUARDRAILS_PORT"]) and http["targetPort"] == "http"


def _set_env(name: str, value: str | None, container: str = SCANNER) -> Callable[[dict], None]:
    def mutate(deploy: dict) -> None:
        c = _container(deploy, container)
        c["env"] = [e for e in c["env"] if e["name"] != name]
        if value is not None:
            c["env"].append({"name": name, "value": value})

    return mutate


def _set_mount(volume: str, path: str) -> Callable[[dict], None]:
    def mutate(deploy: dict) -> None:
        next(m for m in _container(deploy, SCANNER)["volumeMounts"] if m["name"] == volume)["mountPath"] = path

    return mutate


def _set_probe(probe: str, path: str) -> Callable[[dict], None]:
    def mutate(deploy: dict) -> None:
        _container(deploy, SCANNER)[probe]["httpGet"]["path"] = path

    return mutate


def _pre_90(deploy: dict) -> None:
    """The Deployment as #66 left it: open-source server port, config path and probes."""
    _set_env("GUARDRAILS_PORT", None)(deploy)
    _set_env("CONFIG_STORE_PATH", None)(deploy)
    _set_env("DEFAULT_CONFIG_ID", None)(deploy)
    _set_env("NEMO_GUARDRAILS_CONFIG_PATH", "/config")(deploy)
    _set_env("SCANNER_URL", "http://127.0.0.1:8000", container=SIDECAR)(deploy)
    _container(deploy, SCANNER)["ports"][0]["containerPort"] = 8000
    _set_mount("nemo-config", "/config/config.yaml")(deploy)
    _set_mount("nemo-rails", "/config/rails")(deploy)
    _set_probe("readinessProbe", "/v1/rails/configs")(deploy)
    _set_probe("livenessProbe", "/v1/rails/configs")(deploy)


@pytest.mark.static
@pytest.mark.parametrize(
    "mutate,expected",
    [
        (_pre_90, "GUARDRAILS_PORT 7331, its http containerPort is [8000]"),
        (_pre_90, "NEMO_GUARDRAILS_CONFIG_PATH"),
        (_pre_90, "CONFIG_STORE_PATH is unset"),
        (_pre_90, "readinessProbe asks '/v1/rails/configs'"),
        (_set_env("GUARDRAILS_PORT", "8000"), "its http containerPort is [7331]"),
        (_set_env("SCANNER_URL", "http://127.0.0.1:8000", container=SIDECAR), "SCANNER_URL"),
        (_set_env("NEMO_GUARDRAILS_CONFIG_ID", "burrito-bot", container=SIDECAR), "where config id 'burrito-bot' resolves"),
        (_set_env("DEFAULT_CONFIG_ID", "default"), "DEFAULT_CONFIG_ID 'default'"),
        (_set_env("CONFIG_STORE_PATH", "/app/services/guardrails/config-store"), "is not mounted at /app/services"),
        (_set_mount("nemo-config", "/config-store/burritbot/config.yaml"), "not mounted at /config-store/burritbot/config.yml"),
        (_set_mount("nemo-rails", "/config-store/rails"), "not mounted at /config-store/burritbot/rails"),
        (_set_probe("livenessProbe", "/health"), "livenessProbe asks '/health'"),
    ],
    ids=[
        "pre-90-port",
        "pre-90-config-path",
        "pre-90-no-store",
        "pre-90-probe",
        "port-env-drift",
        "adapter-url-drift",
        "adapter-config-id-drift",
        "default-config-id-drift",
        "store-path-drift",
        "config-file-name",
        "rails-outside-config-dir",
        "probe-path",
    ],
)
def test_mutation_microservice_drift_is_caught(mutate: Callable[[dict], None], expected: str) -> None:
    deploy = copy.deepcopy(_deployment(_docs()))
    mutate(deploy)
    violations = microservice_violations(deploy)
    assert any(expected in v for v in violations), violations


# --- live: the microservice serves the burritbot config ---------------------


@pytest.fixture
def forwarded_microservice() -> Iterator[int]:
    """kubectl port-forward to the nemo-guardrails Service's http port. Needs kubectl and the cluster."""
    remote = next(p["port"] for p in _service(_docs())["spec"]["ports"] if p["name"] == "http")
    with port_forward(NAMESPACE, SCANNER, remote) as local:
        yield local


@pytest.mark.live
def test_live_microservice_is_healthy(forwarded_microservice: int) -> None:
    with urllib.request.urlopen(f"http://127.0.0.1:{forwarded_microservice}{HEALTH_PATH}", timeout=10) as resp:
        assert resp.status == 200, f"{HEALTH_PATH} answered {resp.status}"


@pytest.mark.live
def test_live_burritbot_config_id_resolves_and_blocks_act_1(forwarded_microservice: int) -> None:
    """The adapter's exact checks call: the burritbot config is found and the salsa prompt is blocked."""
    env = _env(_container(_deployment(_docs()), SIDECAR))
    payload = adapter.nemo_checks_payload(
        env["NEMO_GUARDRAILS_MODEL"], env["NEMO_GUARDRAILS_CONFIG_ID"], "teach me some salsa dance moves"
    )
    req = urllib.request.Request(
        f"http://127.0.0.1:{forwarded_microservice}{CHECKS_PATH}",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        reply = json.loads(resp.read())
    verdict = adapter.nemo_verdict(reply, payload["messages"][0]["content"])
    assert not verdict.allowed, f"config {env['NEMO_GUARDRAILS_CONFIG_ID']!r} let the Act 1 prompt through: {reply}"
