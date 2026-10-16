# ABOUTME: Static-asset validation helpers — work without a cluster or GCP auth.
# ABOUTME: Used by the offline portions of each phase test (YAML shape, file presence).

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import yaml


def load_yaml(path: Path) -> Any:
    """Load a single-document YAML file and return the parsed structure."""
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def load_yaml_all(path: Path) -> list[Any]:
    """Load a multi-document YAML file and return a list of parsed docs."""
    with path.open("r", encoding="utf-8") as fh:
        return [doc for doc in yaml.safe_load_all(fh) if doc is not None]


def iter_yaml_files(root: Path, pattern: str = "**/*.yaml") -> Iterator[Path]:
    """Iterate YAML files under root matching pattern (default: recursive)."""
    yield from root.glob(pattern)
    yield from root.glob(pattern.replace(".yaml", ".yml"))


def load_json(path: Path) -> Any:
    """Load a JSON file and return the parsed structure."""
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def file_has_aboutme(path: Path) -> bool:
    """Return True if the file begins with two ABOUTME: comment lines.

    The ABOUTME convention is enforced for all code files in this repo
    (Python, Shell, Terraform, Dockerfile, YAML with logic). Pure-docs
    markdown is exempt.
    """
    with path.open("r", encoding="utf-8") as fh:
        lines = []
        for _ in range(4):
            line = fh.readline()
            if not line:
                break
            lines.append(line.strip())
    hits = [ln for ln in lines if "ABOUTME:" in ln]
    return len(hits) >= 2
