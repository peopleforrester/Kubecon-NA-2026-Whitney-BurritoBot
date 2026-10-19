# ABOUTME: Checks that each worktree's pytest session keeps its temp files in that worktree (issue #115).
# ABOUTME: Runs must not depend on the shared /tmp/pytest-of-<user> dir or on /tmp having free inodes.

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from conftest import (
    PROJECT_ROOT,
    WORKTREE_TMP_DIRNAME,
    worktree_basetemp,
    worktree_tmpdir,
)


PROBE = (
    "import os, subprocess, sys, tempfile\n"
    "def test_probe(tmp_path_factory):\n"
    "    child = subprocess.run([sys.executable, '-c', 'import tempfile; print(tempfile.gettempdir())'],\n"
    "                           capture_output=True, text=True, check=True).stdout.strip()\n"
    "    print('\\nBASETEMP=' + str(tmp_path_factory.getbasetemp()))\n"
    "    print('\\nTEMPDIR=' + tempfile.gettempdir())\n"
    "    print('\\nCHILD_TEMPDIR=' + child)\n"
)


def _probe(rootdir: Path, *extra: str, tmpdir_env: str = "") -> dict[str, Path]:
    """Run a real pytest session rooted at `rootdir` with this repo's conftest; return its temp dirs."""
    rootdir.mkdir(parents=True, exist_ok=True)
    probe = rootdir / "test_tmp_probe.py"
    probe.write_text(PROBE)
    env = dict(os.environ, PYTHONPATH=str(PROJECT_ROOT / "tests"), TMPDIR=tmpdir_env)
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-p",
            "conftest",
            "-p",
            "no:cacheprovider",
            "--rootdir",
            str(rootdir),
            "-s",
            *extra,
            str(probe),
        ],
        check=False,
        cwd=rootdir,
        env=env,
        capture_output=True,
        text=True,
        timeout=90,
    )
    assert result.returncode == 0, f"probe session failed:\n{result.stdout}\n{result.stderr}"
    found = dict(ln.split("=", 1) for ln in result.stdout.splitlines() if "DIR=" in ln or "TEMP=" in ln)
    assert found.keys() == {"BASETEMP", "TEMPDIR", "CHILD_TEMPDIR"}, result.stdout
    return {key: Path(value) for key, value in found.items()}


@pytest.mark.static
def test_this_session_keeps_its_temp_files_in_the_worktree(
    given_temp_dirs: tuple[str | None, str | None], tmp_path_factory: pytest.TempPathFactory
) -> None:
    """The suite's tmp_path and tempfile dirs live under this repo's root, unless the run gave its own.

    A runner that starts the suite with TMPDIR (or --basetemp) already set
    keeps it; the unset case is probed in fresh sessions below.
    """
    given_basetemp, given_tmpdir = given_temp_dirs
    basetemp = Path(given_basetemp).resolve() if given_basetemp else worktree_basetemp(PROJECT_ROOT)
    tmpdir = Path(given_tmpdir) if given_tmpdir else worktree_tmpdir(PROJECT_ROOT)
    assert tmp_path_factory.getbasetemp() == basetemp
    assert Path(tempfile.gettempdir()) == tmpdir
    assert os.environ["TMPDIR"] == str(tmpdir)


@pytest.mark.static
def test_two_worktrees_run_in_separate_temp_dirs(tmp_path: Path) -> None:
    """Sessions rooted in two worktrees, TMPDIR unset, each keep temp files in their own root."""
    roots = [tmp_path / "worktree-a", tmp_path / "worktree-b"]
    seen = [_probe(root) for root in roots]
    for root, dirs in zip(roots, seen, strict=True):
        assert dirs == {
            "BASETEMP": worktree_basetemp(root),
            "TEMPDIR": worktree_tmpdir(root),
            "CHILD_TEMPDIR": worktree_tmpdir(root),
        }
    assert seen[0]["BASETEMP"] != seen[1]["BASETEMP"]


@pytest.mark.static
def test_explicit_basetemp_and_tmpdir_win(tmp_path: Path) -> None:
    """A --basetemp on the command line and a TMPDIR already set are used as given."""
    given_basetemp = tmp_path / "given-basetemp"
    given_tmpdir = tmp_path / "given-tmpdir"
    given_tmpdir.mkdir()
    dirs = _probe(tmp_path / "worktree", f"--basetemp={given_basetemp}", tmpdir_env=str(given_tmpdir))
    assert dirs == {
        "BASETEMP": given_basetemp.resolve(),
        "TEMPDIR": given_tmpdir,
        "CHILD_TEMPDIR": given_tmpdir,
    }


@pytest.mark.static
def test_worktree_tmp_dir_is_gitignored() -> None:
    """The per-worktree temp dir never shows up as untracked files."""
    result = subprocess.run(
        ["git", "check-ignore", "-q", f"{WORKTREE_TMP_DIRNAME}/x"],
        cwd=PROJECT_ROOT,
        check=False,
    )
    assert result.returncode == 0, f"{WORKTREE_TMP_DIRNAME}/ is not in .gitignore"
