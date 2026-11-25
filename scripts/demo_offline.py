from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys

from casr.ledger import RequirementLedger
from casr.models import Action, Correction, RequirementVersion
from casr.provenance import ProvenanceGraph
from casr.repair import RepairDecision, RepairPlanner, analyze_impact
from casr.extraction import extract_git_changes
from casr.executor import RepairExecutor
from casr.verifier import IndependentVerifier, TestSpec
from datetime import datetime, timezone
import shutil
import tempfile

from git import Repo

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples" / "offline_export"
NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def commit(repo: Repo, message: str) -> str:
    repo.index.add(list(repo.untracked_files))
    repo.index.commit(message)
    return repo.head.commit.hexsha


def copy_overlay(source: Path, target: Path) -> None:
    for item in source.rglob("*"):
        if item.is_file():
            destination = target / item.relative_to(source)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, destination)


def write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def build_graph(artifacts, correction: Correction) -> ProvenanceGraph:
    graph = ProvenanceGraph()
    for requirement_id, content in {
        "R-xml": "Export XML",
        "R-checksum": "Provide stable checksum",
        "R-summary": "Provide row summary",
        "R-json": correction.content,
    }.items():
        graph.add_requirement_version(
            RequirementVersion(
                requirement_id=requirement_id,
                version=1,
                content=content,
                status="Active",
                created_at=NOW,
            )
        )
    for action_id in ["A-export", "A-json", "A-checksum", "A-summary", "A-cli"]:
        graph.add_action(
            Action(
                action_id=action_id,
                action_type="scripted_edit",
                description=action_id,
                timestamp=NOW,
            )
        )
    for artifact in artifacts:
        graph.add_artifact(artifact)
    relations = [
        ("requirement:R-xml:v1", "action:A-export", "Motivates"),
        ("action:A-export", "artifact:src/exporter.py", "Produces"),
        ("action:A-export", "artifact:src/xml_helpers.py", "Produces"),
        ("action:A-export", "artifact:tests/test_xml_export.py", "Produces"),
        ("requirement:R-json:v1", "action:A-json", "Motivates"),
        ("action:A-json", "artifact:src/exporter.py", "Produces"),
        ("requirement:R-checksum:v1", "action:A-checksum", "Motivates"),
        ("action:A-checksum", "artifact:src/checksum.py", "Produces"),
        ("requirement:R-summary:v1", "action:A-summary", "Motivates"),
        ("action:A-summary", "artifact:src/summary.py", "Produces"),
        ("artifact:src/cli.py", "artifact:src/exporter.py", "Depends-on"),
    ]
    for source, target, relation in relations:
        graph.add_relation(source, target, relation, "manual", 1.0, True)
    return graph


def run(output_dir: Path) -> int:
    output_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="casr-demo-") as temporary:
        temp = Path(temporary)
        workspace = temp / "agent-work"
        shutil.copytree(FIXTURE / "initial_repo", workspace)
        repo = Repo.init(workspace)
        with repo.config_writer() as config:
            config.set_value("user", "name", "CASR Demo")
            config.set_value("user", "email", "casr-demo@example.invalid")
        base_revision = commit(repo, "initial fixture")
        copy_overlay(FIXTURE / "agent_work", workspace)
        correction_revision = commit(repo, "pre-correction agent work")
        artifacts = extract_git_changes(workspace, base_revision, correction_revision)

        correction = Correction.model_validate_json(
            (FIXTURE / "correction.json").read_text(encoding="utf-8")
        )
        ledger = RequirementLedger()
        ledger.add_requirement("R-xml", "Export XML", NOW)
        ledger.add_requirement("R-checksum", "Provide stable checksum", NOW)
        ledger.add_requirement("R-summary", "Provide row summary", NOW)
        ledger.apply_correction(correction)
        graph = build_graph(artifacts, correction)
        analysis = analyze_impact(graph, ledger, correction)
        plan = RepairPlanner(correction.correction_id).plan(analysis, graph)

        repair_workspace = temp / "repair-workspace"
        shutil.copytree(workspace, repair_workspace)
        patch = (FIXTURE / "repair.patch").read_bytes()
        executor = RepairExecutor(repair_workspace, graph)
        records = executor.execute(
            plan,
            {"src/exporter.py": patch},
            temp / "snapshot",
        )
        shutil.copy2(
            FIXTURE / "tests" / "test_json_export.py",
            repair_workspace / "tests" / "test_json_export.py",
        )
        specs = [
            TestSpec(
                test_id="json_export",
                argv=(sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_json_export.py"),
                requirement_ids=["R-json"],
                retention=False,
                timeout_seconds=30,
            ),
            TestSpec(
                test_id="checksum_retention",
                argv=(sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_checksum.py"),
                requirement_ids=["R-checksum"],
                retention=True,
                timeout_seconds=30,
            ),
            TestSpec(
                test_id="summary_retention",
                argv=(sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_summary.py"),
                requirement_ids=["R-summary"],
                retention=True,
                timeout_seconds=30,
            ),
        ]
        report = IndependentVerifier().run(repair_workspace, specs)

        write_json(output_dir / "ledger.json", json.loads(ledger.to_json()))
        write_json(output_dir / "graph.json", graph.to_dict())
        write_json(output_dir / "impact.json", analysis.model_dump(mode="json"))
        write_json(output_dir / "repair_plan.json", plan.model_dump(mode="json"))
        write_json(output_dir / "execution.json", [record.model_dump(mode="json") for record in records])
        write_json(
            output_dir / "verification.json",
            {**report.model_dump(mode="json"), "overall": report.overall},
        )
        shutil.copy2(temp / "snapshot" / "pre_repair.diff", output_dir / "pre_repair.diff")
        write_json(
            output_dir / "run_summary.json",
            {
                "demo_type": "scripted_harness_demo",
                "overall": report.overall,
                "correction_id": correction.correction_id,
                "decision_counts": {
                    kind: sum(decision.kind == kind for decision in plan.decisions)
                    for kind in ["Revert", "Modify", "Revalidate", "Retain"]
                },
                "model_api_called": False,
                "fixture_root": "examples/offline_export",
            },
        )
        executor.repo.close()
        repo.close()
        return 0 if report.overall == "PASS" else 1


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=ROOT / "results" / "offline_demo")
    arguments = parser.parse_args()
    return run(arguments.output_dir)


if __name__ == "__main__":
    raise SystemExit(main())
