from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def test_graph_ablation_measures_recall_and_precision_failures(tmp_path: Path) -> None:
    output_dir = tmp_path / "ablation"
    completed = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "run_graph_ablation.py"),
            "--config",
            str(ROOT / "experiments" / "graph_ablation.json"),
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
    by_variant = {
        variant: [row for row in raw if row["variant"] == variant]
        for variant in ["complete", "missing_provenance", "spurious_dependency"]
    }
    assert all(row["repair_success"] for row in by_variant["complete"])
    assert not any(row["repair_success"] for row in by_variant["missing_provenance"])
    assert all(row["repair_success"] for row in by_variant["spurious_dependency"])
    assert all(
        row["decision_counts"].get("Modify", 0) == 0
        and row["decision_counts"].get("Revert", 0) == 0
        for row in by_variant["missing_provenance"]
    )
    assert all(
        row["decision_counts"]["Revalidate"] > complete["decision_counts"]["Revalidate"]
        and row["decision_counts"]["Retain"] < complete["decision_counts"]["Retain"]
        for row, complete in zip(
            sorted(by_variant["spurious_dependency"], key=lambda item: item["case_id"]),
            sorted(by_variant["complete"], key=lambda item: item["case_id"]),
        )
    )
    assert all(row["retained_modules_rewritten"] == 0 for row in raw)
    summary = json.loads((output_dir / "summary.json").read_text(encoding="utf-8"))
    assert summary["model_api_called"] is False
    assert summary["conclusion"]
    assert (output_dir / "config.json").exists()
    assert (output_dir / "run_metadata.json").exists()
