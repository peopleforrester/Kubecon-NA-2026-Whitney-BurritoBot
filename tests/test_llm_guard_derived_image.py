# ABOUTME: The derived llm-guard-api image (#108): the 0.3.16 base by digest plus spaCy's zh_core_web_sm and spacy-pkuseg,
# ABOUTME: so the Anonymize/Sensitive analyzer finds every model it loads and never pip-installs on the read-only root.

from __future__ import annotations

import copy
import re
import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest
import yaml

from conftest import PROJECT_ROOT
from helpers.image_requirements import DERIVED_IMAGES


(IMAGE,) = (image for image in DERIVED_IMAGES if image.name == "llm-guard-api")
CONFIG = PROJECT_ROOT / "ai-gateway" / "llm-guard" / "config.yaml"

# llm_guard 0.3.16 (tag v0.3.16): Anonymize and Sensitive both call get_analyzer()
# with ALL_SUPPORTED_LANGUAGES = ["en", "zh"] whatever their params say, and
# analyzer._get_nlp_engine() runs spacy.cli.download("<lang>_core_web_sm") for a
# model spacy.util.is_package() does not find. On the pod's read-only root that
# pip install fails and spaCy exits, so the API never starts.
PRESIDIO_SCANNERS = frozenset({"Anonymize", "Sensitive"})
ANALYZER_LANGUAGES = ("en", "zh")

# What the base image already has, from the file listings of its amd64 layers
# (pip layer sha256:515f284b…, model layer sha256:5db83991…), read 2026-10-17.
BASE_PACKAGES = {"spacy": "3.8.6", "numpy": "2.2.6", "en-core-web-sm": "3.8.0"}
# The amd64 image config was created 2025-05-19T14:32Z; PyPI as of the next day.
BASE_BUILT = "2025-05-20T00:00:00Z"

# What the derived layer adds. zh_core_web_sm 3.8.0's meta.json takes spaCy
# >=3.8.0,<3.9.0 and its METADATA requires spacy-pkuseg>=1.0.0,<2.0.0, which
# the base lacks; spacy-pkuseg needs numpy and srsly, which spaCy already brings.
ADDED_PACKAGES = {"spacy-pkuseg": "1.0.1", "zh-core-web-sm": "3.8.0"}
SPACY_MODELS_RELEASES = "https://github.com/explosion/spacy-models/releases/download/"

_PINNED = re.compile(r"^([A-Za-z0-9_.-]+)==(\S+)")
_URL = re.compile(r"^([A-Za-z0-9_.-]+) @ (\S+)")


def _norm(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _blocks(text: str) -> list[str]:
    """Requirement entries, each joined with its `\\` continuation lines."""
    joined = text.replace("\\\n", " ")
    return [line.strip() for line in joined.splitlines() if line.strip() and not line.lstrip().startswith("#")]


def requirement_versions(text: str) -> dict[str, str]:
    """name -> version for `name==version` lines and for `name @ <wheel URL>` lines."""
    out: dict[str, str] = {}
    for block in _blocks(text):
        if match := _PINNED.match(block):
            out[_norm(match.group(1))] = match.group(2)
        elif match := _URL.match(block):
            wheel = match.group(2).rsplit("/", 1)[-1]
            out[_norm(match.group(1))] = wheel.split("-")[1]
        else:
            out[block.split()[0]] = ""
    return out


def requirements_violations(text: str) -> list[str]:
    """Where the requirements file is not exactly the two hashed packages the base lacks."""
    out: list[str] = []
    versions = requirement_versions(text)
    if versions != ADDED_PACKAGES:
        out.append(f"requirements pin {versions}; the base lacks exactly {ADDED_PACKAGES}")
    for block in _blocks(text):
        if "--hash=sha256:" not in block:
            out.append(f"{block.split()[0]} has no --hash=sha256")
        if (match := _URL.match(block)) and not match.group(2).startswith(SPACY_MODELS_RELEASES):
            out.append(f"{match.group(1)} comes from {match.group(2)}, not spaCy's model releases")
    for name, version in versions.items():
        if name.endswith("-core-web-sm") and version.split(".")[:2] != BASE_PACKAGES["spacy"].split(".")[:2]:
            out.append(f"{name} {version} does not match the base's spaCy {BASE_PACKAGES['spacy']}")
    return out


def spacy_model_violations(config: dict, text: str) -> list[str]:
    """Each analyzer language the configured Presidio scanners load needs its spaCy model in the image."""
    used = {
        entry.get("type")
        for section in ("input_scanners", "output_scanners")
        for entry in config.get(section) or []
        if isinstance(entry, dict)
    } & PRESIDIO_SCANNERS
    if not used:
        return []
    have = set(BASE_PACKAGES) | set(requirement_versions(text))
    return [
        f"{sorted(used)} load a {lang} analyzer; {lang}_core_web_sm is not in the image, "
        "so spaCy pip-installs it at startup on a read-only root and the API exits"
        for lang in ANALYZER_LANGUAGES
        if f"{lang}-core-web-sm" not in have
    ]


def _dockerfile_lines(path: Path = IMAGE.dockerfile) -> list[str]:
    text = path.read_text(encoding="utf-8").replace("\\\n", " ")
    return [line.strip() for line in text.splitlines() if line.strip() and not line.lstrip().startswith("#")]


def dockerfile_violations(lines: list[str]) -> list[str]:
    """Where the Dockerfile is more than the pinned base plus one hashed, unresolved, user-site install."""
    out: list[str] = []
    froms = [line.split()[1:] for line in lines if line.upper().startswith("FROM ")]
    if froms != [[IMAGE.base]]:
        out.append(f"FROM {froms}; the base is {IMAGE.base}, pinned by digest")
    installs = [line for line in lines if re.search(r"\bpip\b.*\binstall\b", line)]
    if len(installs) != 1:
        out.append(f"{len(installs)} pip installs: {installs}")
    else:
        (install,) = installs
        for flag in ("--no-deps", "--require-hashes", "--user"):
            if flag not in install:
                out.append(f"pip install lacks {flag}: {install}")
        if not re.search(r"-r \S*requirements\.txt\b", install):
            out.append(f"pip install does not read requirements.txt: {install}")
    for line in lines:
        if re.search(r"\bspacy\s+download\b", line):
            out.append(f"spacy download pip-installs an unhashed model and resolves its dependencies: {line}")
    # The base's uid, HOME, PYTHONPATH and entrypoint stay as they are; #91's checks hold for them.
    for line in lines:
        keyword = line.split()[0].upper()
        if keyword in {"USER", "ENTRYPOINT", "CMD", "ENV", "WORKDIR"}:
            out.append(f"{keyword} overrides the base image: {line}")
    if not any("zh_core_web_sm" in line and "spacy.load" in line for line in lines if line.upper().startswith("RUN ")):
        out.append("no RUN loads zh_core_web_sm, so a broken model would surface only in the pod")
    return out


def _config() -> dict:
    return yaml.safe_load(CONFIG.read_text(encoding="utf-8"))


def _requirements() -> str:
    return IMAGE.requirements.read_text(encoding="utf-8")


@pytest.mark.static
def test_configured_analyzers_find_every_spacy_model() -> None:
    violations = spacy_model_violations(_config(), _requirements())
    assert not violations, "\n  ".join(violations)


@pytest.mark.static
def test_requirements_are_the_two_missing_packages_hashed() -> None:
    violations = requirements_violations(_requirements())
    assert not violations, "\n  ".join(violations)


@pytest.mark.static
def test_dockerfile_extends_the_pinned_base_only() -> None:
    violations = dockerfile_violations(_dockerfile_lines())
    assert not violations, "\n  ".join(violations)


def _drop(name: str) -> Callable[[str], str]:
    def mutate(text: str) -> str:
        return "\n".join(b for b in _blocks(text) if _norm(b.split()[0].split("==")[0]) != name)

    return mutate


def _unhash(text: str) -> str:
    return re.sub(r"\s*--hash=sha256:\S+", "", text.replace("\\\n", " "))


@pytest.mark.static
@pytest.mark.parametrize(
    "mutate,expected",
    [
        (_drop("zh-core-web-sm"), "zh_core_web_sm is not in the image"),
        (_drop("spacy-pkuseg"), "the base lacks exactly"),
        (_unhash, "has no --hash=sha256"),
        (lambda t: t.replace("3.8.0-py3", "3.7.0-py3"), "does not match the base's spaCy"),
        (lambda t: t + "\nnumpy==2.3.0 --hash=sha256:" + "0" * 64, "the base lacks exactly"),
    ],
    ids=["no-zh-model", "no-pkuseg", "unhashed", "model-spacy-minor", "extra-package"],
)
def test_mutation_requirements_drift_is_caught(mutate: Callable[[str], str], expected: str) -> None:
    text = mutate(_requirements())
    violations = requirements_violations(text) + spacy_model_violations(_config(), text)
    assert any(expected in v for v in violations), violations


@pytest.mark.static
def test_mutation_without_presidio_scanners_needs_no_zh_model() -> None:
    config = copy.deepcopy(_config())
    for section in ("input_scanners", "output_scanners"):
        config[section] = [e for e in config[section] if e["type"] not in PRESIDIO_SCANNERS]
    assert spacy_model_violations(config, "") == []


@pytest.mark.static
@pytest.mark.parametrize(
    "mutate,expected",
    [
        (lambda ls: [("FROM laiyer/llm-guard-api:0.3.16" if line.startswith("FROM") else line) for line in ls], "pinned by digest"),
        (lambda ls: [line.replace(" --require-hashes", "") for line in ls], "lacks --require-hashes"),
        (lambda ls: [line.replace(" --no-deps", "") for line in ls], "lacks --no-deps"),
        (lambda ls: [line.replace(" --user", "") for line in ls], "lacks --user"),
        (lambda ls: [*ls, "USER root"], "USER overrides the base image"),
        (lambda ls: [*ls, "ENV PYTHONPATH=/opt/zh"], "ENV overrides the base image"),
        (lambda ls: [*ls, "RUN python -m spacy download zh_core_web_sm"], "spacy download pip-installs"),
        (lambda ls: [line for line in ls if "spacy.load" not in line], "no RUN loads zh_core_web_sm"),
    ],
    ids=["unpinned-base", "no-hashes", "resolves", "system-site", "user", "pythonpath", "spacy-download", "no-load-check"],
)
def test_mutation_dockerfile_drift_is_caught(mutate: Callable[[list[str]], list[str]], expected: str) -> None:
    violations = dockerfile_violations(mutate(_dockerfile_lines()))
    assert any(expected in v for v in violations), violations


@pytest.mark.live
@pytest.mark.timeout(900)
def test_requirements_install_onto_the_base_spacy(tmp_path: Path) -> None:
    """On Python 3.12 with the base's spaCy and numpy, the hashed install loads zh_core_web_sm with nothing missing."""
    uv = shutil.which("uv")
    assert uv, "uv is not on PATH; this test builds a Python 3.12 venv with it"
    venv = tmp_path / "venv"
    subprocess.run([uv, "venv", "--python", "3.12", "--seed", str(venv)], check=True)
    pip = str(venv / "bin" / "pip")
    python = str(venv / "bin" / "python")

    def run(*args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(list(args), capture_output=True, text=True, check=False)

    # The base's spaCy as PyPI resolved it when the image was built, not as it resolves today.
    base = run(
        pip,
        "install",
        "--no-cache-dir",
        f"--uploaded-prior-to={BASE_BUILT}",
        f"spacy=={BASE_PACKAGES['spacy']}",
        f"numpy=={BASE_PACKAGES['numpy']}",
    )
    assert base.returncode == 0, f"installing the base's spaCy failed:\n{base.stdout}\n{base.stderr}"
    # The Dockerfile's flags, minus --user, which a venv refuses.
    added = run(pip, "install", "--no-cache-dir", "--no-deps", "--require-hashes", "-r", str(IMAGE.requirements))
    assert added.returncode == 0, f"the hashed install failed:\n{added.stdout}\n{added.stderr}"
    check = run(pip, "check")
    assert check.returncode == 0, f"the added packages miss a dependency:\n{check.stdout}{check.stderr}"
    load = run(
        python,
        "-c",
        "import spacy, spacy.util; assert spacy.util.is_package('zh_core_web_sm'); "
        "print(spacy.load('zh_core_web_sm')('我想要一个墨西哥卷饼').text)",
    )
    assert load.returncode == 0, f"zh_core_web_sm does not load:\n{load.stdout}\n{load.stderr}"
