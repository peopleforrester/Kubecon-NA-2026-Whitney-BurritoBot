# ABOUTME: Builds the NeMo Guardrails config the cluster mounts and checks messages against it with real LLMRails.
# ABOUTME: Shared by the rail flow tests (#102) and the fallback prompt replay tests (#103).

from __future__ import annotations

import asyncio
from pathlib import Path

import yaml
from nemoguardrails import LLMRails, RailsConfig

from conftest import PROJECT_ROOT


NEMO_DIR = PROJECT_ROOT / "ai-gateway" / "nemo-guardrails"
CONFIGMAP_CONFIG = NEMO_DIR / "configmap-config.yaml"
CONFIGMAP_RAILS = NEMO_DIR / "configmap-rails.yaml"


def configmap_data(path: Path) -> dict[str, str]:
    return yaml.safe_load(path.read_text())["data"]


def mounted_config(root: Path, config_text: str, rails: dict[str, str]) -> RailsConfig:
    """Lay the config out as the Deployment mounts it: <config id>/config.yml beside rails/.

    The Vertex AI models are dropped: no rail here calls a model, and ChatVertexAI
    cannot be built without GCP auth (and #100 questions the engine in 25.07).
    """
    config = yaml.safe_load(config_text)
    del config["models"]
    store = root / "burritbot"
    (store / "rails").mkdir(parents=True)
    (store / "config.yml").write_text(yaml.safe_dump(config))
    for name, text in rails.items():
        (store / "rails" / name).write_text(text)
    return RailsConfig.from_path(str(store))


def mounted_rails(root: Path) -> LLMRails:
    """The burritbot config from the two ConfigMaps the cluster mounts, loaded by real LLMRails."""
    return LLMRails(
        mounted_config(
            root,
            configmap_data(CONFIGMAP_CONFIG)["config.yaml"],
            configmap_data(CONFIGMAP_RAILS),
        )
    )


def check(rails: LLMRails, messages: list[dict]) -> tuple[str, str | None]:
    """Run the rails on messages; return the status ("passed" / "blocked") and the rail that blocked."""
    result = asyncio.run(rails.check_async(messages))
    return result.status.value, result.rail
