from __future__ import annotations

from datetime import datetime
from pathlib import PurePosixPath
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


RequirementStatus = Literal["Active", "Superseded", "Revoked"]
CorrectionType = Literal["ADD", "AMEND", "REVOKE", "SUPERSEDE"]
VerificationStatus = Literal["PASS", "FAIL", "UNKNOWN"]


def _non_empty(value: str) -> str:
    if not value.strip():
        raise ValueError("value must not be empty")
    return value


class RequirementVersion(BaseModel):
    model_config = ConfigDict(frozen=True)

    requirement_id: str
    version: int = Field(ge=1)
    content: str
    status: RequirementStatus
    created_at: datetime
    superseded_by: str | None = None

    _validate_requirement_id = field_validator("requirement_id")(_non_empty)
    _validate_content = field_validator("content")(_non_empty)


class RequirementRecord(BaseModel):
    requirement_id: str
    versions: list[RequirementVersion] = Field(min_length=1)

    @field_validator("requirement_id")
    @classmethod
    def validate_requirement_id(cls, value: str) -> str:
        return _non_empty(value)

    @field_validator("versions")
    @classmethod
    def validate_versions(cls, value: list[RequirementVersion]) -> list[RequirementVersion]:
        if any(item.requirement_id != value[0].requirement_id for item in value):
            raise ValueError("all versions must belong to the same requirement")
        if [item.version for item in value] != list(range(1, len(value) + 1)):
            raise ValueError("versions must be consecutive and start at 1")
        return value

    @property
    def current(self) -> RequirementVersion:
        return self.versions[-1]


class Correction(BaseModel):
    correction_id: str
    correction_type: CorrectionType
    target_requirement_id: str | None = None
    new_requirement_id: str | None = None
    content: str | None = None
    created_at: datetime

    _validate_correction_id = field_validator("correction_id")(_non_empty)


class Action(BaseModel):
    action_id: str
    action_type: str
    description: str
    timestamp: datetime
    related_requirements: list[str] = Field(default_factory=list)
    affected_artifacts: list[str] = Field(default_factory=list)
    execution_result: str | None = None

    _validate_action_id = field_validator("action_id")(_non_empty)


class Artifact(BaseModel):
    artifact_id: str
    path: str
    baseline_blob: str | None = None
    current_blob: str | None = None
    produced_by: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)

    _validate_artifact_id = field_validator("artifact_id")(_non_empty)

    @field_validator("path")
    @classmethod
    def validate_path(cls, value: str) -> str:
        path = PurePosixPath(value)
        if (
            not value
            or "\\" in value
            or path.is_absolute()
            or any(part in {"", ".", ".."} for part in value.split("/"))
            or path.as_posix() != value
        ):
            raise ValueError("path must be a normalized POSIX relative path")
        return value


class Evidence(BaseModel):
    evidence_id: str
    evidence_type: str
    command: list[str]
    status: VerificationStatus
    timestamp: datetime
    related_requirements: list[str] = Field(default_factory=list)
    related_artifacts: list[str] = Field(default_factory=list)
    detail: str = ""

    _validate_evidence_id = field_validator("evidence_id")(_non_empty)
