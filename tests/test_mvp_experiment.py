from __future__ import annotations

import csv
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def test_mvp_synthetic_experiment(tmp_path: Path) -> None:
    output_dir = tmp_path / "experiment"
    completed = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "run_mvp_experiment.py"),
            "--config",
            str(ROOT / "experiments" / "mvp_synthetic.json"),
            "--output-dir",
            str(output_dir),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    raw = json.loads((output_dir / "raw_results.json").read_text(encoding="utf-8"))
    assert len(raw) == 9
    by_policy = {
        policy: [row for row in raw if row["policy"] == policy]
        for policy in ["no_repair", "full_rebuild", "casr_selective"]
    }
    assert all(row["active_requirement"] == "FAIL" for row in by_policy["no_repair"])
    assert all(row["retention"] == "PASS" for row in by_policy["no_repair"])
    assert all(row["repair_success"] for row in by_policy["full_rebuild"])
    assert all(row["repair_success"] for row in by_policy["casr_selective"])
    assert {row["retained_modules_rewritten"] for row in by_policy["casr_selective"]} == {0}
    assert {row["retained_modules_rewritten"] for row in by_policy["full_rebuild"]} == {2, 4, 6}
    assert all(
        selective["total_paths_written"] < rebuilt["total_paths_written"]
        for selective, rebuilt in zip(
            sorted(by_policy["casr_selective"], key=lambda row: row["case_id"]),
            sorted(by_policy["full_rebuild"], key=lambda row: row["case_id"]),
        )
    )
    summary = json.loads((output_dir / "summary.json").read_text(encoding="utf-8"))
    assert summary["experiment_type"] == "synthetic_harness_policy_experiment"
    assert summary["model_api_called"] is False
    assert summary["casr_repair_success_rate"] == 1.0
    assert summary["full_rebuild_repair_success_rate"] == 1.0
    assert "整体重建重写 12 个保留模块" in summary["finding"]
    assert " and " not in summary["finding"]
    with (output_dir / "results.csv").open(encoding="utf-8", newline="") as handle:
        assert len(list(csv.DictReader(handle))) == 9
