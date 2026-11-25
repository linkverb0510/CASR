from __future__ import annotations

import os
from pathlib import Path

import pytest
from git import Repo

from casr.executor import RepairExecutor
from casr.models import Artifact
from casr.provenance import ProvenanceGraph
from casr.repair import RepairDecision, RepairKind, RepairPlan


def add_artifact(
    graph: ProvenanceGraph,
    artifact_id: str,
    path: str,
    baseline_blob: str | None,
    current_blob: str | None = "current",
) -> None:
    graph.add_artifact(
        Artifact(
            artifact_id=artifact_id,
            path=path,
            baseline_blob=baseline_blob,
            current_blob=current_blob,
        )
    )


def make_workspace(tmp_path: Path) -> tuple[Path, Repo, ProvenanceGraph]:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    repo = Repo.init(workspace)
    with repo.config_writer() as config:
        config.set_value("user", "name", "CASR Test")
        config.set_value("user", "email", "casr-test@example.invalid")
    (workspace / "modified.py").write_text("old\n", encoding="utf-8")
    (workspace / "shared.py").write_text("old shared\n", encoding="utf-8")
    repo.index.add(["modified.py", "shared.py"])
    repo.index.commit("base")
    (workspace / "new.py").write_text("new\n", encoding="utf-8")
    (workspace / "modified.py").write_text("agent change\n", encoding="utf-8")
    (workspace / "shared.py").write_text("agent shared\n", encoding="utf-8")

    graph = ProvenanceGraph()
    add_artifact(graph, "new_file", "new.py", None)
    add_artifact(graph, "modified_file", "modified.py", repo.head.commit.tree["modified.py"].hexsha)
    add_artifact(graph, "shared_file", "shared.py", repo.head.commit.tree["shared.py"].hexsha)
    add_artifact(graph, "cli", "cli.py", "base")
    add_artifact(graph, "checksum", "checksum.py", "base")
    return workspace, repo, graph


def test_executor_reverts_modifies_skips_and_snapshots(tmp_path: Path) -> None:
    workspace, repo, graph = make_workspace(tmp_path)
    snapshot_dir = tmp_path / "snapshot"
    patch = (
        b"diff --git a/shared.py b/shared.py\n"
        b"--- a/shared.py\n"
        b"+++ b/shared.py\n"
        b"@@ -1 +1 @@\n"
        b"-agent shared\n"
        b"+repaired shared\n"
    )
    plan = RepairPlan(
        correction_id="C1",
        decisions=[
            RepairDecision(kind="Revert", artifact_id="new_file", reason="test"),
            RepairDecision(kind="Revert", artifact_id="modified_file", reason="test"),
            RepairDecision(kind="Modify", artifact_id="shared_file", reason="test"),
            RepairDecision(kind="Revalidate", artifact_id="cli", reason="test"),
            RepairDecision(kind="Retain", artifact_id="checksum", reason="test"),
        ],
    )
    records = RepairExecutor(workspace, graph).execute(
        plan, {"shared_file": patch}, snapshot_dir
    )

    assert not (workspace / "new.py").exists()
    assert (workspace / "modified.py").read_text(encoding="utf-8") == "old\n"
    assert (workspace / "shared.py").read_text(encoding="utf-8") == "repaired shared\n"
    assert (snapshot_dir / "workspace" / "new.py").read_text(encoding="utf-8") == "new\n"
    assert (snapshot_dir / "pre_repair.diff").exists()
    assert (snapshot_dir / "pre_repair.diff").read_text(encoding="utf-8")
    assert [record.status for record in records] == [
        "applied",
        "applied",
        "applied",
        "skipped",
        "skipped",
    ]


@pytest.mark.parametrize("path", ["../outside.txt", "/absolute.txt"])
def test_executor_rejects_unsafe_paths_without_writing_outside(tmp_path: Path, path: str) -> None:
    workspace, _, graph = make_workspace(tmp_path)
    outside = tmp_path / "outside.txt"
    outside.write_text("unchanged\n", encoding="utf-8")
    graph.add_artifact(
        Artifact.model_construct(
            artifact_id="bad",
            path=path,
            baseline_blob=None,
            current_blob="blob",
            produced_by=[],
            dependencies=[],
            evidence_ids=[],
        )
    )
    plan = RepairPlan(
        correction_id="C1",
        decisions=[RepairDecision(kind="Revert", artifact_id="bad", reason="test")],
    )
    records = RepairExecutor(workspace, graph).execute(plan, {}, tmp_path / "snapshot")
    assert records[0].status == "failed"
    assert outside.read_text(encoding="utf-8") == "unchanged\n"


def test_executor_rejects_symlink_escape(tmp_path: Path) -> None:
    workspace, _, graph = make_workspace(tmp_path)
    outside = tmp_path / "outside.txt"
    outside.write_text("unchanged\n", encoding="utf-8")
    try:
        os.symlink(outside, workspace / "link.py", target_is_directory=False)
    except OSError as exc:
        pytest.skip(f"symlinks unavailable: {exc}")
    add_artifact(graph, "bad", "link.py", None)
    plan = RepairPlan(
        correction_id="C1",
        decisions=[RepairDecision(kind="Revert", artifact_id="bad", reason="test")],
    )
    records = RepairExecutor(workspace, graph).execute(plan, {}, tmp_path / "snapshot")
    assert records[0].status == "failed"
    assert outside.read_text(encoding="utf-8") == "unchanged\n"


def test_executor_rejects_unknown_decision_and_internal_snapshot(tmp_path: Path) -> None:
    workspace, _, graph = make_workspace(tmp_path)
    plan = RepairPlan(
        correction_id="C1",
        decisions=[
            RepairDecision.model_construct(
                kind="Execute", artifact_id="new_file", reason="test"
            )
        ],
    )
    records = RepairExecutor(workspace, graph).execute(plan, {}, tmp_path / "snapshot")
    assert records[0].status == "failed"
    with pytest.raises(ValueError, match="outside"):
        RepairExecutor(workspace, graph).execute(plan, {}, workspace / "snapshot")
