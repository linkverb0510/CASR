from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
LOCAL = ROOT / "scripts" / "local"
CLUSTER = ROOT / "scripts" / "cluster"
WINDOWS_ONLY = pytest.mark.skipif(
    os.name != "nt", reason="local automation scripts require Windows PowerShell"
)


def run_powershell(script: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(script),
            *args,
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
        check=False,
    )


def run_bash(script: Path, *args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    relative_script = script.relative_to(ROOT).as_posix()
    return subprocess.run(
        ["bash", relative_script, *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
        env={**os.environ, **(env or {})},
        check=False,
    )


def dry_run_json(result: subprocess.CompletedProcess[str]) -> dict[str, object]:
    assert result.returncode == 0, result.stderr
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    assert lines, result.stdout
    return json.loads(lines[-1])


@WINDOWS_ONLY
def test_sync_dry_run_reports_plan_without_creating_archive() -> None:
    result = run_powershell(LOCAL / "sync.ps1", "-DryRun")

    plan = dry_run_json(result)

    assert plan["action"] == "sync"
    assert plan["host_alias"] == "casr-cluster"
    assert plan["remote_root"] == "/home/panxg27/CASR"
    assert "scp" in plan["steps"]
    assert "scripts/cluster/prepare.sh" in plan["archive_items"]
    assert "examples" in plan["archive_items"]
    assert "experiments" in plan["archive_items"]


@WINDOWS_ONLY
@pytest.mark.parametrize("remote_root", ["/tmp/../etc", "relative/path", "/tmp/CASR;id"])
def test_sync_rejects_unsafe_remote_root(remote_root: str) -> None:
    result = run_powershell(LOCAL / "sync.ps1", "-DryRun", "-RemoteRoot", remote_root)

    assert result.returncode != 0
    assert "RemoteRoot" in result.stderr


@WINDOWS_ONLY
def test_sync_rejects_unsafe_host_alias() -> None:
    result = run_powershell(LOCAL / "sync.ps1", "-DryRun", "-HostAlias", "casr;id")

    assert result.returncode != 0
    assert "HostAlias" in result.stderr


@WINDOWS_ONLY
def test_smoke_test_dry_run_runs_prepare_and_pytest() -> None:
    result = run_powershell(LOCAL / "smoke-test.ps1", "-DryRun")

    plan = dry_run_json(result)

    assert plan["action"] == "smoke-test"
    assert "scripts/cluster/prepare.sh" in plan["command"]
    assert "pytest" in plan["command"]
    assert "sleep" not in plan["command"]


@WINDOWS_ONLY
def test_collect_dry_run_does_not_create_output(tmp_path: Path) -> None:
    output = tmp_path / "collected"
    result = run_powershell(
        LOCAL / "collect.ps1",
        "-DryRun",
        "-RunId",
        "smoke-001",
        "-OutputDirectory",
        str(output),
    )

    plan = dry_run_json(result)

    assert plan["action"] == "collect"
    assert plan["run_id"] == "smoke-001"
    assert not output.exists()


@WINDOWS_ONLY
def test_collect_rejects_unsafe_run_id() -> None:
    result = run_powershell(LOCAL / "collect.ps1", "-DryRun", "-RunId", "../secret")

    assert result.returncode != 0
    assert "RunId" in result.stderr


def test_cluster_scripts_have_valid_bash_syntax() -> None:
    for script in (CLUSTER / "prepare.sh", CLUSTER / "run_experiment.sh"):
        result = subprocess.run(
            ["bash", "-n", script.relative_to(ROOT).as_posix()],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        assert result.returncode == 0, result.stderr


def test_prepare_rejects_unsafe_root() -> None:
    result = run_bash(CLUSTER / "prepare.sh", "--root", "/tmp/../etc")

    assert result.returncode != 0
    assert "root" in result.stderr.lower()


@WINDOWS_ONLY
def test_prepare_prefers_python312_over_incompatible_python3(tmp_path: Path) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    compatible = bin_dir / "python3.12.exe"
    shutil.copy2(getattr(sys, "_base_executable", sys.executable), compatible)
    bin_posix = subprocess.check_output(
        ["cygpath", "-u", str(bin_dir)], text=True, encoding="utf-8"
    ).strip()
    git_bash = (
        Path(os.environ.get("ProgramFiles", r"C:\Program Files"))
        / "Git"
        / "bin"
        / "bash.exe"
    )
    site_packages = Path(sys.executable).parent.parent / "Lib" / "site-packages"

    result = subprocess.run(
        [
            str(git_bash),
            "-c",
            'PATH="$1:$PATH" bash scripts/cluster/prepare.sh --root /tmp',
            "casr-test",
            bin_posix,
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
        env={**os.environ, "PYTHONPATH": str(site_packages)},
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert '"ready": true' in result.stdout


def test_run_experiment_rejects_unsafe_run_id() -> None:
    result = run_bash(CLUSTER / "run_experiment.sh", "--run-id", "../secret")

    assert result.returncode != 0
    assert "run-id" in result.stderr.lower()


def test_run_experiment_help_exits_without_running_commands() -> None:
    result = run_bash(CLUSTER / "run_experiment.sh", "--help")

    assert result.returncode == 0
    assert "run-id" in result.stdout
    assert "crater job create" not in result.stdout.lower()
    assert "sbatch" not in result.stdout.lower()
