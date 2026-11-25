from __future__ import annotations

from pathlib import Path, PurePosixPath
import shutil
import subprocess

from git import Repo
from pydantic import BaseModel

from casr.provenance import ProvenanceGraph
from casr.repair import RepairKind, RepairPlan


class ExecutionRecord(BaseModel):
    decision_kind: RepairKind
    artifact_id: str
    status: str
    detail: str


class RepairExecutor:
    def __init__(self, workspace: Path, graph: ProvenanceGraph) -> None:
        self.workspace = workspace.resolve()
        self.graph = graph
        self.repo = Repo(self.workspace)

    def _artifact_path(self, artifact_id: str) -> Path:
        artifacts = {
            node["data"]["artifact_id"]: node["data"]
            for node in self.graph.to_dict()["nodes"]
            if node["kind"] == "artifact"
        }
        if artifact_id not in artifacts:
            raise ValueError(f"unknown artifact: {artifact_id}")
        relative = artifacts[artifact_id]["path"]
        if not isinstance(relative, str):
            raise ValueError("artifact path must be a string")
        posix_path = PurePosixPath(relative)
        if (
            not relative
            or "\\" in relative
            or posix_path.is_absolute()
            or any(part in {"", ".", ".."} for part in relative.split("/"))
            or posix_path.as_posix() != relative
        ):
            raise ValueError(f"unsafe artifact path: {relative!r}")
        target = (self.workspace / relative).resolve()
        if not target.is_relative_to(self.workspace):
            raise ValueError(f"artifact path escapes workspace: {relative!r}")
        return target

    def _snapshot(self, snapshot_dir: Path) -> None:
        snapshot_root = snapshot_dir.resolve()
        if snapshot_root.is_relative_to(self.workspace):
            raise ValueError("snapshot directory must be outside the workspace")
        snapshot_root.mkdir(parents=True, exist_ok=False)
        shutil.copytree(
            self.workspace,
            snapshot_root / "workspace",
            ignore=shutil.ignore_patterns(".git"),
        )
        head = self.repo.head.commit
        baseline = head.parents[0].hexsha if head.parents else head.hexsha
        diff = self.repo.git.diff(baseline, "--binary")
        (snapshot_root / "pre_repair.diff").write_text(diff, encoding="utf-8")

    def _revert(self, artifact_id: str, baseline_blob: object) -> None:
        target = self._artifact_path(artifact_id)
        if baseline_blob is None:
            target.unlink(missing_ok=True)
            return
        if not isinstance(baseline_blob, str):
            raise ValueError("baseline blob must be a string")
        content = self.repo.odb.stream(bytes.fromhex(baseline_blob)).read()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)

    def _modify(self, artifact_id: str, patch: bytes) -> None:
        target = self._artifact_path(artifact_id)
        relative = target.relative_to(self.workspace).as_posix()
        base_command = ["git", "apply", "--whitespace=nowarn", f"--include={relative}"]
        checked = subprocess.run(
            [*base_command, "--check", "-"],
            cwd=self.workspace,
            input=patch,
            capture_output=True,
            shell=False,
            check=False,
        )
        if checked.returncode != 0:
            raise ValueError(checked.stderr.decode("utf-8", errors="replace").strip())
        applied = subprocess.run(
            [*base_command, "-"],
            cwd=self.workspace,
            input=patch,
            capture_output=True,
            shell=False,
            check=False,
        )
        if applied.returncode != 0:
            raise ValueError(applied.stderr.decode("utf-8", errors="replace").strip())

    def execute(
        self,
        plan: RepairPlan,
        patches: dict[str, bytes],
        snapshot_dir: Path,
    ) -> list[ExecutionRecord]:
        self._snapshot(snapshot_dir)
        artifacts = {
            node["data"]["artifact_id"]: node["data"]
            for node in self.graph.to_dict()["nodes"]
            if node["kind"] == "artifact"
        }
        records: list[ExecutionRecord] = []
        for decision in plan.decisions:
            if decision.kind not in {"Revert", "Modify", "Revalidate", "Retain"}:
                records.append(
                    ExecutionRecord.model_construct(
                        decision_kind=decision.kind,
                        artifact_id=decision.artifact_id,
                        status="failed",
                        detail="unknown repair decision",
                    )
                )
                continue
            if decision.kind in {"Retain", "Revalidate"}:
                records.append(
                    ExecutionRecord(
                        decision_kind=decision.kind,
                        artifact_id=decision.artifact_id,
                        status="skipped",
                        detail="decision does not modify the workspace",
                    )
                )
                continue
            try:
                if decision.kind == "Revert":
                    self._revert(
                        decision.artifact_id,
                        artifacts[decision.artifact_id]["baseline_blob"],
                    )
                else:
                    if decision.artifact_id not in patches:
                        raise ValueError("missing modification patch")
                    self._modify(decision.artifact_id, patches[decision.artifact_id])
            except (KeyError, OSError, ValueError) as exc:
                records.append(
                    ExecutionRecord(
                        decision_kind=decision.kind,
                        artifact_id=decision.artifact_id,
                        status="failed",
                        detail=str(exc),
                    )
                )
            else:
                records.append(
                    ExecutionRecord(
                        decision_kind=decision.kind,
                        artifact_id=decision.artifact_id,
                        status="applied",
                        detail=decision.reason,
                    )
                )
        return records
