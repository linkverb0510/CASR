from __future__ import annotations

from datetime import datetime
import json

from casr.models import Correction, RequirementRecord, RequirementVersion


class RequirementLedger:
    def __init__(self, records: dict[str, RequirementRecord] | None = None) -> None:
        self._records = records or {}

    def add_requirement(
        self, requirement_id: str, content: str, created_at: datetime
    ) -> RequirementRecord:
        if requirement_id in self._records:
            raise ValueError(f"requirement already exists: {requirement_id}")
        record = RequirementRecord(
            requirement_id=requirement_id,
            versions=[
                RequirementVersion(
                    requirement_id=requirement_id,
                    version=1,
                    content=content,
                    status="Active",
                    created_at=created_at,
                )
            ],
        )
        self._records[requirement_id] = record
        return record

    def apply_correction(self, correction: Correction) -> RequirementRecord:
        if correction.correction_type == "ADD":
            if correction.target_requirement_id is not None:
                raise ValueError("ADD must not target an existing requirement")
            if not correction.new_requirement_id or not correction.content:
                raise ValueError("ADD requires new_requirement_id and content")
            return self.add_requirement(
                correction.new_requirement_id,
                correction.content,
                correction.created_at,
            )

        target_id = correction.target_requirement_id
        if not target_id or target_id not in self._records:
            raise ValueError("correction target requirement does not exist")
        record = self._records[target_id]
        current = record.current
        if current.status != "Active":
            raise ValueError("correction target must be active")

        if correction.correction_type == "AMEND":
            if not correction.content:
                raise ValueError("AMEND requires content")
            if correction.new_requirement_id is not None:
                raise ValueError("AMEND must not create a new requirement id")
            updated = RequirementRecord(
                requirement_id=record.requirement_id,
                versions=[
                    *record.versions[:-1],
                    current.model_copy(update={"status": "Superseded"}),
                    RequirementVersion(
                        requirement_id=record.requirement_id,
                        version=current.version + 1,
                        content=correction.content,
                        status="Active",
                        created_at=correction.created_at,
                    ),
                ],
            )
            self._records[record.requirement_id] = updated
            return updated

        if correction.correction_type == "REVOKE":
            if correction.new_requirement_id is not None:
                raise ValueError("REVOKE must not create a new requirement id")
            updated = RequirementRecord(
                requirement_id=record.requirement_id,
                versions=[
                    *record.versions,
                    RequirementVersion(
                        requirement_id=record.requirement_id,
                        version=current.version + 1,
                        content=current.content,
                        status="Revoked",
                        created_at=correction.created_at,
                    ),
                ],
            )
            self._records[record.requirement_id] = updated
            return updated

        new_id = correction.new_requirement_id
        if not new_id:
            raise ValueError("SUPERSEDE requires new_requirement_id")
        if not correction.content:
            raise ValueError("SUPERSEDE requires content")
        if new_id in self._records:
            raise ValueError(f"requirement already exists: {new_id}")
        superseded = RequirementRecord(
            requirement_id=record.requirement_id,
            versions=[
                *record.versions[:-1],
                current.model_copy(update={"status": "Superseded", "superseded_by": new_id}),
            ],
        )
        self._records[record.requirement_id] = superseded
        return self.add_requirement(new_id, correction.content, correction.created_at)

    def active_requirements(self) -> list[RequirementVersion]:
        return [
            record.current
            for record in self._records.values()
            if record.current.status == "Active"
        ]

    def invalid_versions(self) -> list[RequirementVersion]:
        return [
            version
            for record in self._records.values()
            for version in record.versions
            if version.status != "Active"
        ]

    def get(self, requirement_id: str) -> RequirementRecord:
        try:
            return self._records[requirement_id]
        except KeyError as exc:
            raise ValueError(f"unknown requirement: {requirement_id}") from exc

    def to_json(self) -> str:
        payload = {
            requirement_id: record.model_dump(mode="json")
            for requirement_id, record in self._records.items()
        }
        return json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2)

    @classmethod
    def from_json(cls, payload: str) -> RequirementLedger:
        data = json.loads(payload)
        if not isinstance(data, dict):
            raise ValueError("ledger payload must be a JSON object")
        records = {
            requirement_id: RequirementRecord.model_validate(record)
            for requirement_id, record in data.items()
        }
        return cls(records)
