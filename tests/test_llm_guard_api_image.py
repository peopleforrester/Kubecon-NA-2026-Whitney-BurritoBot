# ABOUTME: The llm-guard Deployment and scanner config against the laiyer/llm-guard-api:0.3.16 image (#91):
# ABOUTME: config path (CONFIG_FILE), config schema (type + params), writable paths for a non-1000 uid, startup and probes.

from __future__ import annotations

import copy
import json
import re
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

LLM_GUARD_DIR = PROJECT_ROOT / "ai-gateway" / "llm-guard"
DEPLOYMENT = LLM_GUARD_DIR / "deployment.yaml"
CONFIGMAP = LLM_GUARD_DIR / "configmap.yaml"
CONFIG = LLM_GUARD_DIR / "config.yaml"
NAMESPACE = "burritbot-net"
SCANNER = "llm-guard"
SIDECAR = "burritbot-extproc"
CONFIG_CONFIGMAP = "llm-guard-config"

# The image, read from Docker Hub and from the llm_guard_api source at tag
# v0.3.16 (github.com/protectai/llm-guard, archived 2026-07-08; 0.3.16 is the
# last release on Docker Hub and PyPI). The image's app layer is byte-identical
# to that tag's llm_guard_api/app, config/scanners.yml and entrypoint.sh.
# - Image config: User "user" (uid 1000), HOME=/home/user, WORKDIR /home/user/app,
#   ENTRYPOINT ./entrypoint.sh, EXPOSE 8000. Every file under /home/user is
#   world-readable and its directories world-executable, so another non-root uid
#   can run it; the packages live in the user site /home/user/.local, found via HOME.
# - app/app.py create_app(): the config file is os.getenv("CONFIG_FILE",
#   "./config/scanners.yml"). Nothing reads LLM_GUARD_CONFIG.
# - entrypoint.sh: uvicorn on --port=8000, --workers=$APP_WORKERS.
UPSTREAM_IMAGE = "laiyer/llm-guard-api:0.3.16"
# The pod runs the derived image (#108, ai-gateway/llm-guard/Dockerfile): the
# upstream image by digest plus spaCy's zh_core_web_sm, which Anonymize and
# Sensitive load. Its tag is the upstream version plus a burritbot build number.
IMAGE = "us-west1-docker.pkg.dev/kk-community-projects/burritbot/llm-guard-api:0.3.16-burritbot.1"
IMAGE_HOME = "/home/user"
API_PORT = 8000
HEALTH_PATHS = frozenset({"/healthz", "/readyz"})
ANALYZE_PROMPT = "/analyze/prompt"
ANALYZE_OUTPUT = "/analyze/output"

# app/config.py: Config, AppConfig and the tracing/metrics exporter Literals.
# Pydantic drops unknown keys silently, so a key outside these sets does nothing.
CONFIG_KEYS = frozenset({"input_scanners", "output_scanners", "rate_limit", "auth", "app", "tracing", "metrics"})
APP_KEYS = frozenset(
    {"name", "log_level", "log_json", "scan_fail_fast", "scan_prompt_timeout", "scan_output_timeout", "lazy_load"}
)
TRACING_EXPORTERS = frozenset({"otel_http", "console"})
METRICS_EXPORTERS = frozenset({"otel_http", "prometheus", "console"})
SCANNER_ENTRY_KEYS = frozenset({"type", "params"})

# app/scanner.py hands each entry's params to the llm_guard 0.3.16 scanner as
# keyword arguments (get_scanner_by_name(name, params) -> Scanner(**params)), so
# an unknown key is a TypeError at startup. It sets model, use_onnx, vault and
# recognizer_conf itself. For the scanners it loads a model for it also reads,
# and removes, these tuning keys.
MODEL_TUNING_KEYS = frozenset({"model_path", "model_batch_size", "model_max_length", "model_onnx_file_name"})


def _scanner(required: set[str], optional: set[str], model: bool) -> dict:
    return {"required": frozenset(required), "allowed": frozenset(required | optional), "model": model}


# Constructor keywords of the llm_guard 0.3.16 scanners this config uses, minus
# what the API injects. A scanner missing here has not been checked against 0.3.16.
INPUT_SCANNERS = {
    "Anonymize": _scanner(
        set(),
        {"hidden_names", "allowed_names", "entity_types", "preamble", "regex_patterns", "use_faker", "threshold", "language"},
        model=True,
    ),
    "BanSubstrings": _scanner({"substrings"}, {"match_type", "case_sensitive", "redact", "contains_all"}, model=False),
    "BanTopics": _scanner({"topics"}, {"threshold"}, model=True),
    "Language": _scanner({"valid_languages"}, {"threshold", "match_type"}, model=True),
    "PromptInjection": _scanner(set(), {"threshold", "match_type"}, model=True),
    "TokenLimit": _scanner(set(), {"limit", "encoding_name", "model_name"}, model=False),
}
OUTPUT_SCANNERS = {
    "Bias": _scanner(set(), {"threshold", "match_type"}, model=True),
    "MaliciousURLs": _scanner(set(), {"threshold"}, model=True),
    "NoRefusal": _scanner(set(), {"threshold", "match_type"}, model=True),
    "Regex": _scanner({"patterns"}, {"is_blocked", "match_type", "redact"}, model=False),
    "Sensitive": _scanner(set(), {"entity_types", "regex_patterns", "redact", "threshold"}, model=True),
}

# The ONNX files each scanner downloads into the Hugging Face cache, in MiB, from
# the Hub file listings of the repos and revisions llm_guard 0.3.16 pins
# (model.onnx plus tokenizer files). Anonymize and Sensitive share one model.
MODEL_DOWNLOAD_MIB = {
    "ProtectAI/deberta-v3-base-prompt-injection-v2": 713,
    "MoritzLaurer/deberta-v3-base-zeroshot-v2.0": 713,
    "ProtectAI/xlm-roberta-base-language-detection-onnx": 1077,
    "Isotonic/deberta-v3-base_finetuned_ai4privacy_v2": 713,
    "ProtectAI/distilroberta-base-rejection-v1": 314,
    "ProtectAI/distilroberta-bias-onnx": 314,
    "ProtectAI/codebert-base-Malicious_URLs-onnx": 476,
}
SCANNER_MODEL = {
    "PromptInjection": "ProtectAI/deberta-v3-base-prompt-injection-v2",
    "BanTopics": "MoritzLaurer/deberta-v3-base-zeroshot-v2.0",
    "Language": "ProtectAI/xlm-roberta-base-language-detection-onnx",
    "Anonymize": "Isotonic/deberta-v3-base_finetuned_ai4privacy_v2",
    "Sensitive": "Isotonic/deberta-v3-base_finetuned_ai4privacy_v2",
    "NoRefusal": "ProtectAI/distilroberta-base-rejection-v1",
    "Bias": "ProtectAI/distilroberta-bias-onnx",
    "MaliciousURLs": "ProtectAI/codebert-base-Malicious_URLs-onnx",
}


def _docs(path=DEPLOYMENT) -> list[dict]:
    with path.open(encoding="utf-8") as fp:
        return [d for d in yaml.safe_load_all(fp) if d]


def _deployment() -> dict:
    return next(d for d in _docs() if d["kind"] == "Deployment")


def _configmap() -> dict:
    return next(d for d in _docs(CONFIGMAP) if d["kind"] == "ConfigMap")


def _config() -> dict:
    with CONFIG.open(encoding="utf-8") as fp:
        return yaml.safe_load(fp)


def _container(deploy: dict, name: str) -> dict:
    return next(c for c in deploy["spec"]["template"]["spec"]["containers"] if c["name"] == name)


def _env(container: dict) -> dict[str, str]:
    return {e["name"]: e["value"] for e in container.get("env") or []}


def _mib(quantity: str) -> float:
    for suffix, factor in (("Gi", 1024), ("Mi", 1)):
        if quantity.endswith(suffix):
            return float(quantity[: -len(suffix)]) * factor
    raise AssertionError(f"unparseable quantity {quantity!r}")


def config_violations(config: dict) -> list[str]:
    """Where the scanner config disagrees with the 0.3.16 API's Config schema and scanner constructors."""
    out: list[str] = []
    if not isinstance(config, dict):
        return [f"config is not a mapping: {config!r}"]
    for key in sorted(set(config) - CONFIG_KEYS):
        out.append(f"top-level key {key!r} is not in the API's Config; it is dropped unread")
    # The adapter posts without credentials, so any auth block refuses every call.
    if "auth" in config:
        out.append("auth is set; the burritbot-extproc adapter sends no credentials and every /analyze call would be refused")
    app = config.get("app") or {}
    for key in sorted(set(app) - APP_KEYS):
        out.append(f"app.{key} is not in the API's AppConfig; it is dropped unread")
    # Lazy loading builds the scanners on the first request, past the adapter's
    # timeout, and once per concurrent request. Eager loading finishes before
    # uvicorn listens, so the probes report a pod that can actually scan.
    if app.get("lazy_load") is not False:
        out.append(f"app.lazy_load is {app.get('lazy_load')!r}; the scanners must load before the API listens")
    for block, exporters in (("tracing", TRACING_EXPORTERS), ("metrics", METRICS_EXPORTERS)):
        if block in config and (config[block] or {}).get("exporter") not in exporters:
            out.append(f"{block}.exporter {(config[block] or {}).get('exporter')!r} is not one of {sorted(exporters)}")

    for section, known in (("input_scanners", INPUT_SCANNERS), ("output_scanners", OUTPUT_SCANNERS)):
        entries = config.get(section)
        if not entries:
            out.append(f"{section} is missing or empty")
            continue
        for i, entry in enumerate(entries):
            where = f"{section}[{i}]"
            if not isinstance(entry, dict):
                out.append(f"{where} is not a mapping")
                continue
            for key in sorted(set(entry) - SCANNER_ENTRY_KEYS):
                out.append(f"{where} has key {key!r}; a scanner entry is type plus params")
            kind = entry.get("type")
            if kind not in known:
                out.append(f"{where} type {kind!r} has not been checked against llm_guard 0.3.16")
                continue
            params = entry.get("params") or {}
            spec = known[kind]
            allowed = spec["allowed"] | (MODEL_TUNING_KEYS if spec["model"] else frozenset())
            for key in sorted(set(params) - allowed):
                out.append(f"{where} {kind} params.{key} is not a {kind} argument in llm_guard 0.3.16")
            for key in sorted(spec["required"] - set(params)):
                out.append(f"{where} {kind} needs params.{key}")
    return out


def deployment_violations(deploy: dict, config: dict, configmap: dict) -> list[str]:
    """Where the Deployment disagrees with the 0.3.16 image or with the adapter in front of it."""
    out: list[str] = []
    pod = deploy["spec"]["template"]["spec"]
    scanner = _container(deploy, SCANNER)
    env = _env(scanner)
    adapter_env = _env(_container(deploy, SIDECAR))

    if scanner["image"] == UPSTREAM_IMAGE:
        out.append(
            f"{SCANNER} runs {UPSTREAM_IMAGE!r}, which lacks zh_core_web_sm; "
            f"Anonymize and Sensitive need {IMAGE}, built from ai-gateway/llm-guard/Dockerfile"
        )
    elif scanner["image"] != IMAGE:
        out.append(f"{SCANNER} runs {scanner['image']!r}; these checks hold for {IMAGE}")

    # Port: entrypoint.sh hardcodes uvicorn --port=8000.
    http = [p["containerPort"] for p in scanner.get("ports") or [] if p.get("name") == "http"]
    if http != [API_PORT]:
        out.append(f"{SCANNER} http containerPort is {http}; the image's uvicorn listens on {API_PORT}")
    if adapter_env.get("SCANNER_URL") != f"http://127.0.0.1:{API_PORT}":
        out.append(f"the adapter's SCANNER_URL {adapter_env.get('SCANNER_URL')!r} is not the API's port {API_PORT}")

    # Config path: create_app() reads CONFIG_FILE; it must name the mounted ConfigMap key.
    if "LLM_GUARD_CONFIG" in env:
        out.append("LLM_GUARD_CONFIG is read by nothing in the image; the API takes its config path from CONFIG_FILE")
    volumes = {v["name"]: v for v in pod.get("volumes") or []}
    mounts = scanner.get("volumeMounts") or []
    config_file = env.get("CONFIG_FILE")
    if not config_file:
        out.append("CONFIG_FILE is unset; the API would load the image's built-in ./config/scanners.yml")
    else:
        source = next(
            (
                m
                for m in mounts
                if m["mountPath"] == config_file
                and (volumes.get(m["name"]) or {}).get("configMap", {}).get("name") == CONFIG_CONFIGMAP
            ),
            None,
        )
        if source is None:
            out.append(f"CONFIG_FILE {config_file!r} is not where ConfigMap {CONFIG_CONFIGMAP} is mounted")
        elif source.get("subPath") not in (configmap.get("data") or {}):
            out.append(f"the mount at {config_file} takes key {source.get('subPath')!r}, which {CONFIG_CONFIGMAP} lacks")

    # uid: the image's packages are found through HOME, and every file is world-readable,
    # so any non-root uid runs it. What it writes must land on emptyDirs, because the
    # root filesystem is read-only: the Hugging Face cache and /tmp (tiktoken's cache).
    if env.get("HOME", IMAGE_HOME) != IMAGE_HOME:
        out.append(f"HOME is {env['HOME']!r}; the image's packages live in {IMAGE_HOME}/.local and are found through HOME")
    empty_dirs = {m["mountPath"]: volumes[m["name"]] for m in mounts if "emptyDir" in volumes.get(m["name"], {})}

    def writable(path: str) -> dict | None:
        return next(
            (v for mount, v in empty_dirs.items() if path == mount or path.startswith(mount.rstrip("/") + "/")), None
        )

    hf_home = env.get("HF_HOME")
    if not hf_home:
        out.append("HF_HOME is unset; the model cache must be named, not left to the image's HOME")
    elif writable(hf_home) is None:
        out.append(f"HF_HOME {hf_home!r} is on the read-only root filesystem, not an emptyDir")
    else:
        models = {
            SCANNER_MODEL[e.get("type")]
            for section in ("input_scanners", "output_scanners")
            for e in config.get(section) or []
            if isinstance(e, dict) and e.get("type") in SCANNER_MODEL
        }
        need = sum(MODEL_DOWNLOAD_MIB[m] for m in models)
        limit = writable(hf_home)["emptyDir"].get("sizeLimit")
        if limit is not None and _mib(limit) < need * 1.2:
            out.append(f"the cache at HF_HOME is capped at {limit}; the configured scanners download {need} MiB")
    if writable("/tmp") is None:
        out.append("/tmp is not an emptyDir; tiktoken (TokenLimit) caches its encodings there")
    for mount in empty_dirs:
        if mount.startswith("/home/") and not mount.startswith(IMAGE_HOME + "/"):
            out.append(f"emptyDir at {mount} is outside the image's HOME {IMAGE_HOME}; nothing in the image writes there")

    # Startup: with lazy_load false the API listens only once every scanner is loaded,
    # after the first start has downloaded the models. A startupProbe holds liveness off.
    for probe in ("startupProbe", "readinessProbe", "livenessProbe"):
        get = (scanner.get(probe) or {}).get("httpGet") or {}
        if get.get("path") not in HEALTH_PATHS:
            out.append(f"{SCANNER} {probe} asks {get.get('path')!r}; the API serves health at {sorted(HEALTH_PATHS)}")
        elif get.get("port") not in ("http", API_PORT):
            out.append(f"{SCANNER} {probe} probes port {get.get('port')!r}, not the API's {API_PORT}")
    return out


@pytest.mark.static
def test_config_matches_the_0_3_16_schema() -> None:
    violations = config_violations(_config())
    assert not violations, "config.yaml disagrees with llm-guard-api 0.3.16:\n  " + "\n  ".join(violations)


@pytest.mark.static
def test_configmap_carries_config_yaml() -> None:
    carried = yaml.safe_load(_configmap()["data"]["config.yaml"])
    assert carried == _config(), "configmap.yaml data.config.yaml has drifted from ai-gateway/llm-guard/config.yaml"


@pytest.mark.static
def test_deployment_matches_the_0_3_16_image() -> None:
    violations = deployment_violations(_deployment(), _config(), _configmap())
    assert not violations, "llm-guard disagrees with llm-guard-api 0.3.16:\n  " + "\n  ".join(violations)


@pytest.mark.static
def test_adapter_calls_the_0_3_16_analyze_paths() -> None:
    import inspect

    source = inspect.getsource(adapter.LlmGuard)
    for path in (ANALYZE_PROMPT, ANALYZE_OUTPUT):
        assert f'"{path}"' in source, f"the adapter no longer posts to {path}"


# Version pins in the agent rules, specs, skills and delivery docs.
VERSION_DOCS = ("AGENTS.md", "spec/**/*.md", ".claude/skills/*.md", "presentations/*/docs/*.md", "presentations/*/spec/*.md")
LLM_GUARD_VERSION_CLAIM = re.compile(r"LLM Guard\W+(?:The Net\W+)?(\d+\.\d+\.\d+\+?)")


def version_claims() -> list[tuple[str, str]]:
    return [
        (f"{path.relative_to(PROJECT_ROOT)}:{n}", m.group(1))
        for pattern in VERSION_DOCS
        for path in sorted(PROJECT_ROOT.glob(pattern))
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        for m in LLM_GUARD_VERSION_CLAIM.finditer(line)
    ]


@pytest.mark.static
def test_docs_pin_the_deployed_version() -> None:
    """0.3.16 is the last release; a "0.3.17+" pin names a version that does not exist."""
    tag = UPSTREAM_IMAGE.rsplit(":", 1)[1]
    assert IMAGE.rsplit(":", 1)[1].startswith(f"{tag}-"), f"{IMAGE} is not tagged as a build of {UPSTREAM_IMAGE}"
    claims = version_claims()
    assert claims, "no LLM Guard version pin found in the docs"
    wrong = [f"{where} says {version}" for where, version in claims if version != tag]
    assert not wrong, f"docs disagree with the deployed {UPSTREAM_IMAGE}:\n  " + "\n  ".join(wrong)


@pytest.mark.static
def test_version_claim_pattern_catches_the_pre_91_pins() -> None:
    for line in ("- LLM Guard: 0.3.17+", "| LLM Guard | The Net | 0.3.17+ | RED |", "- LLM Guard: **0.3.17+** (both"):
        assert [m.group(1) for m in LLM_GUARD_VERSION_CLAIM.finditer(line)] == ["0.3.17+"], line


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


def _set_probe(probe: str, path: str | None) -> Callable[[dict], None]:
    def mutate(deploy: dict) -> None:
        c = _container(deploy, SCANNER)
        if path is None:
            c.pop(probe, None)
        else:
            c[probe]["httpGet"]["path"] = path

    return mutate


def _set_size_limit(volume: str, limit: str) -> Callable[[dict], None]:
    def mutate(deploy: dict) -> None:
        v = next(v for v in deploy["spec"]["template"]["spec"]["volumes"] if v["name"] == volume)
        v["emptyDir"]["sizeLimit"] = limit

    return mutate


def _set_image(image: str) -> Callable[[dict], None]:
    def mutate(deploy: dict) -> None:
        _container(deploy, SCANNER)["image"] = image

    return mutate


def _pre_91(deploy: dict) -> None:
    """The Deployment as #66 left it: 0.3.9, LLM_GUARD_CONFIG, the cache under a HOME the image does not use."""
    _container(deploy, SCANNER)["image"] = "laiyer/llm-guard-api:0.3.9"
    _set_env("CONFIG_FILE", None)(deploy)
    _set_env("HF_HOME", None)(deploy)
    _set_env("LLM_GUARD_CONFIG", "/config/config.yaml")(deploy)
    _set_mount("hf-cache", "/home/llm-guard/.cache/huggingface")(deploy)
    _set_probe("startupProbe", None)(deploy)


@pytest.mark.static
@pytest.mark.parametrize(
    "mutate,expected",
    [
        (_pre_91, "runs 'laiyer/llm-guard-api:0.3.9'"),
        (_pre_91, "LLM_GUARD_CONFIG is read by nothing"),
        (_pre_91, "CONFIG_FILE is unset"),
        (_pre_91, "HF_HOME is unset"),
        (_pre_91, "emptyDir at /home/llm-guard/.cache/huggingface is outside the image's HOME"),
        (_pre_91, "startupProbe asks None"),
        (_set_env("CONFIG_FILE", "/home/user/app/config/scanners.yml"), "is not where ConfigMap llm-guard-config is mounted"),
        (_set_mount("llm-guard-config", "/config/scanners.yml"), "is not where ConfigMap llm-guard-config is mounted"),
        (_set_env("HOME", "/home/llm-guard"), "HOME is '/home/llm-guard'"),
        (_set_env("HF_HOME", "/home/user/app/.hf"), "is on the read-only root filesystem"),
        (_set_size_limit("hf-cache", "4Gi"), "capped at 4Gi"),
        (_set_mount("tmp", "/var/tmp"), "/tmp is not an emptyDir"),
        (_set_env("SCANNER_URL", "http://127.0.0.1:8080", container=SIDECAR), "SCANNER_URL"),
        (_set_probe("readinessProbe", "/v1/health"), "readinessProbe asks '/v1/health'"),
        (_set_image(UPSTREAM_IMAGE), "which lacks zh_core_web_sm"),
    ],
    ids=[
        "pre-91-image",
        "pre-91-config-env",
        "pre-91-no-config-file",
        "pre-91-no-hf-home",
        "pre-91-cache-path",
        "pre-91-no-startup-probe",
        "config-file-built-in",
        "config-mount-drift",
        "home-override",
        "hf-home-read-only",
        "cache-too-small",
        "no-tmp",
        "adapter-url-drift",
        "probe-path",
        "pre-108-upstream-image",
    ],
)
def test_mutation_deployment_drift_is_caught(mutate: Callable[[dict], None], expected: str) -> None:
    deploy = copy.deepcopy(_deployment())
    mutate(deploy)
    violations = deployment_violations(deploy, _config(), _configmap())
    assert any(expected in v for v in violations), violations


# The config as #66 left it: flat scanner keys, enabled flags, cache/telemetry blocks.
PRE_91_CONFIG = {
    "app": {"name": "burritbot-llm-guard", "namespace": "burritbot-net", "log_level": "INFO"},
    "cache": {"type": "memory", "ttl_seconds": 300},
    "input_scanners": [
        {"type": "TokenLimit", "enabled": True, "max_tokens": 1024, "encoding": "cl100k_base"},
        {"type": "BanTopics", "enabled": True, "threshold": 0.6, "topics": ["dancing"]},
    ],
    "output_scanners": [{"type": "NoRefusal", "enabled": True, "threshold": 0.7}],
    "telemetry": {"otel_endpoint": "http://otel-collector.monitoring.svc.cluster.local:4317"},
}


def _pre_91_config(config: dict) -> None:
    config.clear()
    config.update(copy.deepcopy(PRE_91_CONFIG))


def _scanner_params(section: str, kind: str, **params) -> Callable[[dict], None]:
    def mutate(config: dict) -> None:
        next(e for e in config[section] if e["type"] == kind)["params"].update(params)

    return mutate


@pytest.mark.static
@pytest.mark.parametrize(
    "mutate,expected",
    [
        (_pre_91_config, "top-level key 'cache'"),
        (_pre_91_config, "top-level key 'telemetry'"),
        (_pre_91_config, "app.namespace is not in the API's AppConfig"),
        (_pre_91_config, "has key 'enabled'; a scanner entry is type plus params"),
        (_pre_91_config, "BanTopics needs params.topics"),
        (_pre_91_config, "app.lazy_load is None"),
        (_scanner_params("input_scanners", "TokenLimit", max_tokens=1024), "TokenLimit params.max_tokens"),
        (_scanner_params("input_scanners", "BanSubstrings", model_max_length=256), "BanSubstrings params.model_max_length"),
        (_scanner_params("input_scanners", "PromptInjection", model="x"), "PromptInjection params.model is not"),
        (_scanner_params("output_scanners", "Sensitive", enabled=True), "Sensitive params.enabled"),
        (lambda c: c["input_scanners"].append({"type": "Toxicity", "params": {}}), "type 'Toxicity' has not been checked"),
        (lambda c: c.update(auth={"type": "http_bearer", "token": ""}), "auth is set"),
        (lambda c: c["app"].update(lazy_load=True), "app.lazy_load is True"),
        (lambda c: c.update(tracing={"exporter": "otlp_grpc"}), "tracing.exporter 'otlp_grpc'"),
        (lambda c: c.update(output_scanners=[]), "output_scanners is missing or empty"),
    ],
    ids=[
        "pre-91-cache",
        "pre-91-telemetry",
        "pre-91-app-namespace",
        "pre-91-flat-keys",
        "pre-91-params-missing",
        "pre-91-lazy",
        "token-limit-old-key",
        "tuning-on-modelless-scanner",
        "model-is-the-api-s",
        "enabled-is-no-argument",
        "unchecked-scanner",
        "auth",
        "lazy-load",
        "tracing-exporter",
        "no-output-scanners",
    ],
)
def test_mutation_config_drift_is_caught(mutate: Callable[[dict], None], expected: str) -> None:
    config = copy.deepcopy(_config())
    mutate(config)
    violations = config_violations(config)
    assert any(expected in v for v in violations), violations


# --- live: the scanner loads this config and answers the adapter ------------


@pytest.fixture
def forwarded_api() -> Iterator[int]:
    """kubectl port-forward to the llm-guard Service's http port. Needs kubectl and the cluster."""
    service = next(d for d in _docs() if d["kind"] == "Service")
    remote = next(p["port"] for p in service["spec"]["ports"] if p["name"] == "http")
    with port_forward(NAMESPACE, SCANNER, remote) as local:
        yield local


def _post(port: int, path: str, payload: dict) -> object:
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}{path}",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read())


@pytest.mark.live
def test_live_api_is_ready(forwarded_api: int) -> None:
    with urllib.request.urlopen(f"http://127.0.0.1:{forwarded_api}/readyz", timeout=10) as resp:
        assert resp.status == 200, f"/readyz answered {resp.status}"


@pytest.mark.live
def test_live_prompt_scan_runs_this_config(forwarded_api: int) -> None:
    """The adapter's exact call: this config's input scanners run and BanTopics blocks the Act 1 prompt."""
    reply = _post(forwarded_api, ANALYZE_PROMPT, {"prompt": "teach me some salsa dance moves"})
    verdict = adapter.llm_guard_verdict(reply, "sanitized_prompt")
    configured = {e["type"] for e in _config()["input_scanners"]}
    assert set(verdict.findings) == configured, f"the API ran {sorted(verdict.findings)}, the config lists {sorted(configured)}"
    assert not verdict.allowed, f"the Act 1 prompt passed the input scanners: {reply}"


@pytest.mark.live
def test_live_output_scan_runs_this_config(forwarded_api: int) -> None:
    reply = _post(
        forwarded_api,
        ANALYZE_OUTPUT,
        {"prompt": "what is in a carnitas burrito?", "output": "Carnitas, rice, beans, salsa and cheese."},
    )
    verdict = adapter.llm_guard_verdict(reply, "sanitized_output")
    configured = {e["type"] for e in _config()["output_scanners"]}
    assert set(verdict.findings) == configured, f"the API ran {sorted(verdict.findings)}, the config lists {sorted(configured)}"
