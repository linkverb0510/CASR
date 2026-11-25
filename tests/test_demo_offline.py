from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples" / "offline_export"


def fixture_hashes() -> dict[str, str]:
    return {
        path.relative_to(FIXTURE).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(FIXTURE.rglob("*"))
        if path.is_file()
    }


def test_offline_demo_end_to_end(tmp_path: Path) -> None:
    before = fixture_hashes()
    output_dir = tmp_path / "output"
    completed = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "demo_offline.py"), "--output-dir", str(output_dir)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert fixture_hashes() == before

    ledger = json.loads((output_dir / "ledger.json").read_text(encoding="utf-8"))
    assert ledger["R-xml"]["versions"][0]["status"] == "Superseded"
    assert ledger["R-json"]["versions"][-1]["status"] == "Active"

    plan = json.loads((output_dir / "repair_plan.json").read_text(encoding="utf-8"))
    decisions = {item["artifact_id"]: item["kind"] for item in plan["decisions"]}
    assert set(decisions.values()) == {"Revert", "Modify", "Revalidate", "Retain"}
    assert decisions["src/exporter.py"] == "Modify"
    assert decisions["src/xml_helpers.py"] == "Revert"
    assert decisions["tests/test_xml_export.py"] == "Revert"
    assert decisions["src/cli.py"] == "Revalidate"
    assert decisions["src/checksum.py"] == "Retain"
    assert decisions["src/summary.py"] == "Retain"

    verification = json.loads((output_dir / "verification.json").read_text(encoding="utf-8"))
    assert verification["overall"] == "PASS"
    assert {item["test_id"] for item in verification["results"]} == {
        "json_export",
        "checksum_retention",
        "summary_retention",
    }
    summary = json.loads((output_dir / "run_summary.json").read_text(encoding="utf-8"))
    assert summary["demo_type"] == "scripted_harness_demo"
    assert summary["model_api_called"] is False
    assert (output_dir / "pre_repair.diff").stat().st_size > 0
