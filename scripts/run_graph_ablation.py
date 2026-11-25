from __future__ import annotations

import argparse
from collections import Counter
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile

from git import Repo

from casr.executor import RepairExecutor
from casr.extraction import extract_git_changes
from casr.ledger import RequirementLedger
from casr.models import Correction
from casr.provenance import ProvenanceGraph
from casr.repair import RepairPlanner, analyze_impact
from casr.verifier import IndependentVerifier
from run_mvp_experiment import (
    NOW,
    ROOT,
    JSON_TEST,
    build_graph,
    case_files,
    commit_all,
    make_patch,
    verifier_specs,
    write_file,
)


def variant_graph(base: ProvenanceGraph, variant: str) -> ProvenanceGraph:
    payload = base.to_dict()
    if variant == "missing_provenance":
        payload["edges"] = [
            edge
            for edge in payload["edges"]
            if not (
                edge["source"] == "requirement:R-xml:v1"
                and edge["target"] == "action:A-xml"
                and edge["relation"] == "Motivates"
            )
        ]
    elif variant == "spurious_dependency":
        payload["edges"].append(
            {
                "source": "artifact:src/checksum.py",
                "target": "artifact:src/exporter.py",
                "relation": "Depends-on",
                "relation_source": "test",
                "confidence": 1.0,
                "human_verified": True,
            }
        )
    elif variant != "complete":
        raise ValueError(f"unknown graph variant: {variant}")
    return ProvenanceGraph.from_dict(payload)


def run_variant(
    variant: str,
    case_id: str,
    retained_count: int,
    case_root: Path,
    agent_workspace: Path,
    artifacts,
) -> dict[str, object]:
    graph = variant_graph(build_graph(artifacts, retained_count), variant)
    ledger = RequirementLedger()
    ledger.add_requirement("R-xml", "Export XML", NOW)
    ledger.add_requirement("R-checksum", "Checksum", NOW)
    ledger.add_requirement("R-summary", "Summary", NOW)
    ledger.add_requirement("R-retained", "Retained modules", NOW)
    correction = Correction(
        correction_id=f"C-{case_id}-{variant}",
        correction_type="SUPERSEDE",
        target_requirement_id="R-xml",
        new_requirement_id="R-json",
        content="Export JSON",
        created_at=NOW,
    )
    ledger.apply_correction(correction)
    analysis = analyze_impact(graph, ledger, correction)
    plan = RepairPlanner(correction.correction_id).plan(analysis, graph)

    workspace = case_root / variant
    shutil.copytree(agent_workspace, workspace)
    write_file(workspace, "tests/test_json_export.py", JSON_TEST)
    executor = RepairExecutor(workspace, graph)
    try:
        records = executor.execute(
            plan,
            {"src/exporter.py": make_patch()},
            case_root / f"snapshot-{variant}",
        )
    finally:
        executor.repo.close()
    report = IndependentVerifier().run(workspace, verifier_specs())
    statuses = {result.test_id: result.status for result in report.results}
    decision_counts = Counter(decision.kind for decision in plan.decisions)
    applied = [record for record in records if record.status == "applied"]
    return {
        "case_id": case_id,
        "variant": variant,
        "retained_modules": retained_count,
        "repair_success": statuses["active_json"] == "PASS"
        and statuses["retention"] == "PASS",
        "active_requirement": statuses["active_json"],
        "retention": statuses["retention"],
        "decision_count": len(plan.decisions),
        "decision_counts": dict(sorted(decision_counts.items())),
        "applied_count": len(applied),
        "total_paths_written": 1 + sum(
            record.decision_kind != "Revert" for record in applied
        ),
        "paths_deleted": sum(record.decision_kind == "Revert" for record in applied),
        "retained_modules_rewritten": 0,
        "impact": analysis.model_dump(mode="json"),
        "repair_plan": plan.model_dump(mode="json"),
        "execution": [record.model_dump(mode="json") for record in records],
        "verification": report.model_dump(mode="json"),
        "graph": graph.to_dict(),
    }


def code_revision() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, stderr=subprocess.DEVNULL
        ).strip()
    except subprocess.CalledProcessError:
        return "unknown"


def run(config_path: Path, output_dir: Path) -> None:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if config["repetitions"] != 1:
        raise ValueError("this ablation supports exactly one repetition")
    output_dir.mkdir(parents=True, exist_ok=True)
    raw: list[dict[str, object]] = []
    with tempfile.TemporaryDirectory(prefix="casr-graph-ablation-") as temporary:
        temp = Path(temporary)
        for case in config["cases"]:
            case_id = case["case_id"]
            retained_count = case["retained_modules"]
            base_files, agent_files, _ = case_files(retained_count)
            case_root = temp / case_id
            workspace = case_root / "agent-workspace"
            workspace.mkdir(parents=True)
            for relative, content in base_files.items():
                write_file(workspace, relative, content)
            repo = Repo.init(workspace)
            with repo.config_writer() as writer:
                writer.set_value("user", "name", "CASR Experiment")
                writer.set_value("user", "email", "casr-experiment@example.invalid")
            commit_all(repo, "base")
            base_revision = repo.head.commit.hexsha
            for relative, content in agent_files.items():
                write_file(workspace, relative, content)
            commit_all(repo, "pre-correction")
            artifacts = extract_git_changes(workspace, base_revision, repo.head.commit.hexsha)
            repo.close()
            for variant in config["variants"]:
                raw.append(
                    run_variant(
                        variant, case_id, retained_count, case_root, workspace, artifacts
                    )
                )

    raw.sort(key=lambda row: (row["case_id"], row["variant"]))
    (output_dir / "raw_results.json").write_text(
        json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    with (output_dir / "results.csv").open("w", encoding="utf-8", newline="") as handle:
        fields = [
            "case_id", "variant", "retained_modules", "repair_success",
            "active_requirement", "retention", "decision_count", "applied_count",
            "total_paths_written", "paths_deleted", "retained_modules_rewritten",
        ]
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(raw)
    variants: dict[str, object] = {}
    for variant in config["variants"]:
        rows = [row for row in raw if row["variant"] == variant]
        variants[variant] = {
            "repair_success_rate": sum(row["repair_success"] for row in rows) / len(rows),
            "mean_decision_count": sum(row["decision_count"] for row in rows) / len(rows),
            "mean_revalidate_count": sum(
                row["decision_counts"].get("Revalidate", 0) for row in rows
            ) / len(rows),
            "mean_retain_count": sum(
                row["decision_counts"].get("Retain", 0) for row in rows
            ) / len(rows),
            "mean_paths_written": sum(row["total_paths_written"] for row in rows) / len(rows),
        }
    summary = {
        "experiment_type": "synthetic_provenance_fidelity_ablation",
        "experiment_id": config["experiment_id"],
        "model_api_called": False,
        "case_count": len(config["cases"]),
        "run_count": len(raw),
        "variants": variants,
        "conclusion": (
            "在该合成设定中，漏记需求到动作的溯源使 3/3 案例无法启动修复；"
            "加入一条伪依赖仍通过 3/3 验收，但把保留产物从 Retain 推到 Revalidate。"
            "因此溯源召回是正确性瓶颈，精度主要影响复核范围。"
        ),
        "limitations": [
            "三个案例共享同一模板，只改变保留模块数量，不能代表真实项目多样性。",
            "伪依赖是人为注入的单边扰动，未测量真实 Agent 的溯源误差分布。",
            "Revalidate 只扩大验证/复核计划，本实验的脚本化补丁未模拟额外人工成本。",
            "单次运行，无统计显著性检验，未调用模型 API。",
        ],
    }
    (output_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    metadata = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "python": sys.version,
        "platform": platform.platform(),
        "code_revision": code_revision(),
        "working_tree_dirty": bool(
            subprocess.check_output(
                ["git", "status", "--porcelain"], cwd=ROOT, text=True,
                stderr=subprocess.DEVNULL,
            ).strip()
        ),
        "command": f"uv run python scripts/run_graph_ablation.py --config {config_path} --output-dir {output_dir}",
    }
    (output_dir / "run_metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    shutil.copy2(config_path, output_dir / "config.json")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=ROOT / "experiments" / "graph_ablation.json")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "results" / "graph_ablation")
    arguments = parser.parse_args()
    run(arguments.config, arguments.output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
