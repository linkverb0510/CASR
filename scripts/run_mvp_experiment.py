from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import difflib
import hashlib
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
from casr.models import Action, Correction, RequirementVersion
from casr.provenance import ProvenanceGraph
from casr.repair import RepairPlanner, analyze_impact
from casr.verifier import IndependentVerifier, TestSpec

ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)

OLD_EXPORTER = '''import csv
import xml.etree.ElementTree as ET


def read_rows(path):
    with open(path, newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def export_xml(rows):
    root = ET.Element("rows")
    for row in rows:
        item = ET.SubElement(root, "row")
        for key, value in row.items():
            ET.SubElement(item, key).text = value
    return ET.tostring(root, encoding="unicode")
'''

NEW_EXPORTER = '''import csv
import json


def read_rows(path):
    with open(path, newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def export_json(rows):
    return json.dumps(rows, ensure_ascii=False, sort_keys=True)
'''

TEST_PREFIX = '''import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

'''

JSON_TEST = TEST_PREFIX + '''from exporter import export_json, read_rows


class JsonExportTest(unittest.TestCase):
    def test_exports_json(self):
        rows = read_rows("data/input.csv")
        payload = export_json(rows)
        self.assertIn('"name": "alice"', payload)
        self.assertNotIn("<row>", payload)


if __name__ == "__main__":
    unittest.main()
'''

RETENTION_TEST = TEST_PREFIX + '''import importlib

from checksum import checksum_rows
from exporter import read_rows
from summary import summarize


class RetentionTest(unittest.TestCase):
    def test_retained_modules(self):
        rows = read_rows("data/input.csv")
        self.assertEqual(len(checksum_rows(rows)), 64)
        self.assertEqual(summarize(rows), {"count": 3, "total": 60})
        for index in range(RETAINED_COUNT):
            module = importlib.import_module(f"retained_{index}")
            self.assertEqual(module.VALUE, index)


if __name__ == "__main__":
    unittest.main()
'''


def write_file(root: Path, relative: str, content: str) -> None:
    target = root / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def commit_all(repo: Repo, message: str) -> None:
    repo.index.add(list(repo.untracked_files))
    repo.index.commit(message)


def case_files(retained_count: int) -> tuple[dict[str, str], dict[str, str], dict[str, str]]:
    base = {
        "README.md": "Synthetic CASR case\n",
        "data/input.csv": "name,value\nalice,10\nbob,20\ncarol,30\n",
    }
    agent = {
        "src/exporter.py": OLD_EXPORTER,
        "src/xml_helpers.py": "import xml.etree.ElementTree as ET\n",
        "src/checksum.py": "import hashlib\n\ndef checksum_rows(rows):\n    return hashlib.sha256(repr(rows).encode()).hexdigest()\n",
        "src/summary.py": "def summarize(rows):\n    return {'count': len(rows), 'total': sum(int(row['value']) for row in rows)}\n",
        "src/cli.py": "from exporter import read_rows\n\ndef main():\n    return read_rows('data/input.csv')\n",
        "tests/test_checksum.py": TEST_PREFIX + "from checksum import checksum_rows\nfrom exporter import read_rows\n\nclass ChecksumTest(unittest.TestCase):\n    def test_checksum(self):\n        self.assertEqual(len(checksum_rows(read_rows('data/input.csv'))), 64)\n",
        "tests/test_summary.py": TEST_PREFIX + "from summary import summarize\nfrom exporter import read_rows\n\nclass SummaryTest(unittest.TestCase):\n    def test_summary(self):\n        self.assertEqual(summarize(read_rows('data/input.csv'))['total'], 60)\n",
    }
    for index in range(retained_count):
        agent[f"src/retained_{index}.py"] = f"VALUE = {index}\n"
    agent["tests/test_retained.py"] = RETENTION_TEST.replace(
        "RETAINED_COUNT", str(retained_count)
    )
    final = dict(agent)
    final.pop("src/xml_helpers.py")
    final["src/exporter.py"] = NEW_EXPORTER
    final["tests/test_json_export.py"] = JSON_TEST
    return base, agent, final


def make_patch() -> bytes:
    lines = list(
        difflib.unified_diff(
            OLD_EXPORTER.splitlines(keepends=True),
            NEW_EXPORTER.splitlines(keepends=True),
            fromfile="a/src/exporter.py",
            tofile="b/src/exporter.py",
        )
    )
    return ("diff --git a/src/exporter.py b/src/exporter.py\n" + "".join(lines)).encode()


def build_graph(artifacts, retained_count: int) -> ProvenanceGraph:
    graph = ProvenanceGraph()
    requirements = {
        "R-xml": "Export XML",
        "R-json": "Export JSON",
        "R-checksum": "Checksum",
        "R-summary": "Summary",
        "R-retained": "Retained modules",
    }
    for requirement_id, content in requirements.items():
        graph.add_requirement_version(
            RequirementVersion(
                requirement_id=requirement_id,
                version=1,
                content=content,
                status="Active",
                created_at=NOW,
            )
        )
    actions = ["A-xml", "A-json", "A-checksum", "A-summary", "A-retained"]
    for action_id in actions:
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
        ("requirement:R-xml:v1", "action:A-xml", "Motivates"),
        ("action:A-xml", "artifact:src/exporter.py", "Produces"),
        ("action:A-xml", "artifact:src/xml_helpers.py", "Produces"),
        ("requirement:R-json:v1", "action:A-json", "Motivates"),
        ("action:A-json", "artifact:src/exporter.py", "Produces"),
        ("requirement:R-checksum:v1", "action:A-checksum", "Motivates"),
        ("action:A-checksum", "artifact:src/checksum.py", "Produces"),
        ("requirement:R-summary:v1", "action:A-summary", "Motivates"),
        ("action:A-summary", "artifact:src/summary.py", "Produces"),
        ("requirement:R-retained:v1", "action:A-retained", "Motivates"),
        ("artifact:src/cli.py", "artifact:src/exporter.py", "Depends-on"),
    ]
    relations.extend(
        ("action:A-retained", f"artifact:src/retained_{index}.py", "Produces")
        for index in range(retained_count)
    )
    for source, target, relation in relations:
        graph.add_relation(source, target, relation, "manual", 1.0, True)
    return graph


def verifier_specs() -> list[TestSpec]:
    return [
        TestSpec(
            test_id="active_json",
            argv=(sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_json_export.py"),
            requirement_ids=["R-json"],
            retention=False,
            timeout_seconds=30,
        ),
        TestSpec(
            test_id="retention",
            argv=(sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_retained.py"),
            requirement_ids=["R-checksum", "R-summary", "R-retained"],
            retention=True,
            timeout_seconds=30,
        ),
    ]


def run_policy(
    policy: str,
    case_root: Path,
    agent_workspace: Path,
    base_files: dict[str, str],
    final_files: dict[str, str],
    graph: ProvenanceGraph,
    plan,
    retained_count: int,
) -> dict[str, object]:
    workspace = case_root / policy
    written: list[str] = []
    deleted: list[str] = []
    if policy == "full_rebuild":
        workspace.mkdir()
        for relative, content in base_files.items():
            write_file(workspace, relative, content)
        for relative, content in final_files.items():
            write_file(workspace, relative, content)
            written.append(relative)
    else:
        shutil.copytree(agent_workspace, workspace)
        write_file(workspace, "tests/test_json_export.py", JSON_TEST)
        written.append("tests/test_json_export.py")
        if policy == "casr_selective":
            executor = RepairExecutor(workspace, graph)
            try:
                records = executor.execute(
                    plan,
                    {"src/exporter.py": make_patch()},
                    case_root / "snapshot",
                )
            finally:
                executor.repo.close()
            artifacts = {
                node["data"]["artifact_id"]: node["data"]
                for node in graph.to_dict()["nodes"]
                if node["kind"] == "artifact"
            }
            for record in records:
                if record.status != "applied":
                    continue
                relative = artifacts[record.artifact_id]["path"]
                if record.decision_kind == "Revert" and artifacts[record.artifact_id]["baseline_blob"] is None:
                    deleted.append(relative)
                else:
                    written.append(relative)
    report = IndependentVerifier().run(workspace, verifier_specs())
    statuses = {result.test_id: result.status for result in report.results}
    active = statuses["active_json"]
    retention = statuses["retention"]
    return {
        "policy": policy,
        "active_requirement": active,
        "retention": retention,
        "repair_success": active == "PASS" and retention == "PASS",
        "total_paths_written": len(written),
        "paths_deleted": len(deleted),
        "retained_modules_rewritten": sum(
            path.startswith("src/retained_") for path in written
        ),
        "written_paths": sorted(written),
        "deleted_paths": sorted(deleted),
        "verification": report.model_dump(mode="json"),
        "duration_seconds": sum(result.duration_seconds for result in report.results),
        "retained_modules": retained_count,
    }


def file_hashes(files: dict[str, str]) -> dict[str, str]:
    return {
        path: hashlib.sha256(content.encode("utf-8")).hexdigest()
        for path, content in sorted(files.items())
    }


def run(config_path: Path, output_dir: Path) -> None:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if config["repetitions"] != 1:
        raise ValueError("this MVP experiment supports exactly one repetition")
    output_dir.mkdir(parents=True, exist_ok=True)
    raw: list[dict[str, object]] = []
    manifests: dict[str, object] = {}
    with tempfile.TemporaryDirectory(prefix="casr-mvp-experiment-") as temporary:
        temp = Path(temporary)
        for case in config["cases"]:
            case_id = case["case_id"]
            retained_count = case["retained_modules"]
            base_files, agent_files, final_files = case_files(retained_count)
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
            correction_revision = repo.head.commit.hexsha
            artifacts = extract_git_changes(workspace, base_revision, correction_revision)
            graph = build_graph(artifacts, retained_count)
            ledger = RequirementLedger()
            ledger.add_requirement("R-xml", "Export XML", NOW)
            ledger.add_requirement("R-checksum", "Checksum", NOW)
            ledger.add_requirement("R-summary", "Summary", NOW)
            ledger.add_requirement("R-retained", "Retained modules", NOW)
            correction = Correction(
                correction_id=f"C-{case_id}",
                correction_type="SUPERSEDE",
                target_requirement_id="R-xml",
                new_requirement_id="R-json",
                content="Export JSON",
                created_at=NOW,
            )
            ledger.apply_correction(correction)
            plan = RepairPlanner(correction.correction_id).plan(
                analyze_impact(graph, ledger, correction), graph
            )
            repo.close()
            manifests[case_id] = {
                "retained_modules": retained_count,
                "pre_correction_files": file_hashes(agent_files),
                "expected_final_files": file_hashes(final_files),
                "repair_plan": plan.model_dump(mode="json"),
            }
            for policy in config["policies"]:
                row = run_policy(
                    policy,
                    case_root,
                    workspace,
                    base_files,
                    final_files,
                    graph,
                    plan,
                    retained_count,
                )
                raw.append({"case_id": case_id, **row})

    raw.sort(key=lambda row: (row["case_id"], row["policy"]))
    (output_dir / "raw_results.json").write_text(
        json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (output_dir / "case_manifests.json").write_text(
        json.dumps(manifests, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    with (output_dir / "results.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(raw[0]))
        writer.writeheader()
        writer.writerows(raw)
    policy_names = config["policies"]
    summary: dict[str, object] = {
        "experiment_type": "synthetic_harness_policy_experiment",
        "experiment_id": config["experiment_id"],
        "model_api_called": False,
        "case_count": len(config["cases"]),
        "run_count": len(raw),
        "policies": {},
        "limitations": [
            "合成案例与脚本化修复策略，不是自主 Coding Agent Benchmark。",
            "单次运行、无统计显著性检验；仅验证 Harness 决策机制与工程闭环。",
            "整体重建使用已知正确最终实现，未模拟重新发现需求的成本。",
        ],
    }
    for policy in policy_names:
        rows = [row for row in raw if row["policy"] == policy]
        summary["policies"][policy] = {
            "repair_success_rate": sum(row["repair_success"] for row in rows) / len(rows),
            "active_requirement_pass_rate": sum(row["active_requirement"] == "PASS" for row in rows) / len(rows),
            "retention_pass_rate": sum(row["retention"] == "PASS" for row in rows) / len(rows),
            "mean_total_paths_written": sum(row["total_paths_written"] for row in rows) / len(rows),
            "retained_modules_rewritten_total": sum(row["retained_modules_rewritten"] for row in rows),
        }
    summary["casr_repair_success_rate"] = summary["policies"]["casr_selective"]["repair_success_rate"]
    summary["full_rebuild_repair_success_rate"] = summary["policies"]["full_rebuild"]["repair_success_rate"]
    rebuilt_retained = summary["policies"]["full_rebuild"]["retained_modules_rewritten_total"]
    casr_retained = summary["policies"]["casr_selective"]["retained_modules_rewritten_total"]
    summary["finding"] = (
        "在本合成设定中，CASR 与整体重建均通过新需求和保留功能验收；"
        f"CASR 重写 {casr_retained} 个保留模块，整体重建重写 {rebuilt_retained} 个保留模块。"
    )
    (output_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    try:
        code_revision = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, stderr=subprocess.DEVNULL
        ).strip()
    except subprocess.CalledProcessError:
        code_revision = "unknown"
    metadata = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "python": sys.version,
        "platform": platform.platform(),
        "code_revision": code_revision,
        "working_tree_dirty": bool(
            subprocess.check_output(
                ["git", "status", "--porcelain"], cwd=ROOT, text=True, stderr=subprocess.DEVNULL
            ).strip()
        ),
        "config": config,
        "command": f"uv run python scripts/run_mvp_experiment.py --config {config_path} --output-dir {output_dir}",
    }
    (output_dir / "run_metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    shutil.copy2(config_path, output_dir / "config.json")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=ROOT / "experiments" / "mvp_synthetic.json")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "results" / "mvp_experiment")
    arguments = parser.parse_args()
    run(arguments.config, arguments.output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
