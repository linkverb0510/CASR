from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from casr.models import Action, Artifact, Correction, Evidence, RequirementRecord, RequirementVersion


NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def version(**overrides: object) -> RequirementVersion:
    values = {
        "requirement_id": "R1",
        "version": 1,
        "content": "Export JSON",
        "status": "Active",
        "created_at": NOW,
        "superseded_by": None,
    }
    values.update(overrides)
    return RequirementVersion(**values)


@pytest.mark.parametrize(
    "overrides",
    [
        {"requirement_id": ""},
        {"content": "  "},
        {"version": 0},
        {"status": "Invalid"},
    ],
)
def test_requirement_version_rejects_invalid_values(overrides: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        version(**overrides)


def test_requirement_version_is_immutable() -> None:
    item = version()
    with pytest.raises(ValidationError):
        item.content = "Changed"  # type: ignore[misc]


def test_requirement_record_current_returns_last_version() -> None:
    first = version()
    second = version(version=2, content="Export JSON and CSV", status="Superseded")
    record = RequirementRecord(requirement_id="R1", versions=[first, second])

    assert record.current == second


@pytest.mark.parametrize("path", ["", "/abs/file.py", "../file.py", "a/../b.py", "./a.py", "a//b.py", "a\\b.py"])
def test_artifact_rejects_non_normalized_posix_relative_path(path: str) -> None:
    with pytest.raises(ValidationError):
        Artifact(artifact_id="A1", path=path)


def test_artifact_accepts_normalized_relative_path() -> None:
    artifact = Artifact(artifact_id="A1", path="src/pkg/file.py")

    assert artifact.path == "src/pkg/file.py"
    assert artifact.produced_by == []
    assert artifact.dependencies == []
    assert artifact.evidence_ids == []


def test_correction_rejects_unknown_type() -> None:
    with pytest.raises(ValidationError):
        Correction(
            correction_id="C1",
            correction_type="INVALID",  # type: ignore[arg-type]
            created_at=NOW,
        )


def test_action_and_evidence_preserve_relations() -> None:
    action = Action(
        action_id="ACT1",
        action_type="write_file",
        description="Write exporter",
        timestamp=NOW,
        related_requirements=["R1"],
        affected_artifacts=["exporter"],
    )
    evidence = Evidence(
        evidence_id="E1",
        evidence_type="test",
        command=["python", "-m", "unittest"],
        status="PASS",
        timestamp=NOW,
        related_requirements=["R1"],
        related_artifacts=["exporter"],
        detail="passed",
    )

    assert action.execution_result is None
    assert evidence.command == ["python", "-m", "unittest"]
    assert evidence.status == "PASS"
