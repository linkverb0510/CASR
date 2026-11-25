from __future__ import annotations

import sys
from pathlib import Path

from casr.verifier import IndependentVerifier, TestSpec


def spec(test_id: str, statement: str, *, retention: bool = False) -> TestSpec:
    return TestSpec(
        test_id=test_id,
        argv=(sys.executable, "-c", statement),
        requirement_ids=[test_id],
        retention=retention,
        timeout_seconds=5,
    )


def test_verifier_pass_fail_and_retention_fields(tmp_path: Path) -> None:
    specs = [
        spec("new", "print('new requirement ok')"),
        spec("old", "print('retained')", retention=True),
    ]
    report = IndependentVerifier().run(tmp_path, specs)
    assert report.overall == "PASS"
    assert all(result.status == "PASS" for result in report.results)
    assert specs[0].retention is False
    assert specs[1].retention is True


def test_verifier_missing_command_timeout_and_empty_specs_are_unknown(tmp_path: Path) -> None:
    missing = TestSpec(
        test_id="missing",
        argv=("casr-command-that-does-not-exist",),
        requirement_ids=["R1"],
        retention=False,
        timeout_seconds=1,
    )
    timeout = TestSpec(
        test_id="timeout",
        argv=(sys.executable, "-c", "import time; time.sleep(2)"),
        requirement_ids=["R1"],
        retention=False,
        timeout_seconds=0.05,
    )
    assert IndependentVerifier().run(tmp_path, [missing]).overall == "UNKNOWN"
    assert IndependentVerifier().run(tmp_path, [timeout]).overall == "UNKNOWN"
    assert IndependentVerifier().run(tmp_path, []).overall == "UNKNOWN"


def test_verifier_fail_dominates_unknown_and_output_is_truncated(tmp_path: Path) -> None:
    failing = spec("fail", "import sys; print('x' * 9000); sys.exit(1)")
    unknown = TestSpec(
        test_id="unknown",
        argv=("casr-command-that-does-not-exist",),
        requirement_ids=["R1"],
        retention=False,
        timeout_seconds=1,
    )
    report = IndependentVerifier().run(tmp_path, [unknown, failing])
    assert report.overall == "FAIL"
    failed = next(result for result in report.results if result.test_id == "fail")
    assert failed.status == "FAIL"
    assert len(failed.stdout) == 8000
    assert failed.return_code == 1
