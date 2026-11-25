from __future__ import annotations

from pathlib import Path
import subprocess
import time
from typing import Literal

from pydantic import BaseModel, Field


class TestSpec(BaseModel):
    __test__ = False

    test_id: str
    argv: tuple[str, ...] = Field(min_length=1)
    requirement_ids: list[str] = Field(default_factory=list)
    retention: bool = False
    timeout_seconds: float = Field(gt=0)


class TestResult(BaseModel):
    __test__ = False

    test_id: str
    status: Literal["PASS", "FAIL", "UNKNOWN"]
    return_code: int | None
    duration_seconds: float
    stdout: str
    stderr: str
    reason: str


class VerificationReport(BaseModel):
    results: list[TestResult] = Field(default_factory=list)

    @property
    def overall(self) -> Literal["PASS", "FAIL", "UNKNOWN"]:
        statuses = {result.status for result in self.results}
        if "FAIL" in statuses:
            return "FAIL"
        if "UNKNOWN" in statuses or not statuses:
            return "UNKNOWN"
        return "PASS"


def _text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def _redact(value: str | bytes | None, workspace: Path) -> str:
    text = _text(value)
    workspace_text = str(workspace.resolve())
    return (
        text.replace(workspace_text, "<workspace>")
        .replace(str(workspace), "<workspace>")
        .replace(str(Path.home().resolve()), "<user-home>")
        .replace(str(Path.home()), "<user-home>")[:8000]
    )


class IndependentVerifier:
    def run(self, workspace: Path, specs: list[TestSpec]) -> VerificationReport:
        results: list[TestResult] = []
        for spec in specs:
            started = time.monotonic()
            try:
                completed = subprocess.run(
                    spec.argv,
                    cwd=workspace,
                    shell=False,
                    capture_output=True,
                    text=True,
                    timeout=spec.timeout_seconds,
                    check=False,
                )
            except subprocess.TimeoutExpired as exc:
                results.append(
                    TestResult(
                        test_id=spec.test_id,
                        status="UNKNOWN",
                        return_code=None,
                        duration_seconds=time.monotonic() - started,
                        stdout=_redact(exc.stdout, workspace),
                        stderr=_redact(exc.stderr, workspace),
                        reason="test command timed out",
                    )
                )
            except OSError as exc:
                results.append(
                    TestResult(
                        test_id=spec.test_id,
                        status="UNKNOWN",
                        return_code=None,
                        duration_seconds=time.monotonic() - started,
                        stdout="",
                        stderr="",
                        reason=f"test command could not start: {_redact(str(exc), workspace)}",
                    )
                )
            else:
                status = "PASS" if completed.returncode == 0 else "FAIL"
                results.append(
                    TestResult(
                        test_id=spec.test_id,
                        status=status,
                        return_code=completed.returncode,
                        duration_seconds=time.monotonic() - started,
                        stdout=_redact(completed.stdout, workspace),
                        stderr=_redact(completed.stderr, workspace),
                        reason="command exited successfully" if status == "PASS" else "command exited non-zero",
                    )
                )
        return VerificationReport(results=results)
