from __future__ import annotations

from datetime import datetime, timezone

import pytest

from casr.ledger import RequirementLedger
from casr.models import Correction


NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def correction(kind: str, **overrides: object) -> Correction:
    values: dict[str, object] = {
        "correction_id": f"C-{kind}",
        "correction_type": kind,
        "created_at": NOW,
    }
    values.update(overrides)
    return Correction(**values)  # type: ignore[arg-type]


def test_add_creates_active_v1() -> None:
    ledger = RequirementLedger()

    record = ledger.apply_correction(
        correction("ADD", new_requirement_id="R1", content="Export JSON")
    )

    assert record.current.requirement_id == "R1"
    assert record.current.version == 1
    assert record.current.status == "Active"
    assert ledger.active_requirements() == [record.current]


def test_amend_preserves_id_and_supersedes_old_version() -> None:
    ledger = RequirementLedger()
    ledger.add_requirement("R1", "Export JSON", NOW)

    record = ledger.apply_correction(
        correction("AMEND", target_requirement_id="R1", content="Export JSON and CSV")
    )

    assert [item.version for item in record.versions] == [1, 2]
    assert record.versions[0].status == "Superseded"
    assert record.current.content == "Export JSON and CSV"
    assert record.current.status == "Active"


def test_supersede_marks_old_requirement_and_creates_new_active_requirement() -> None:
    ledger = RequirementLedger()
    old = ledger.add_requirement("R1", "Export XML", NOW)

    new = ledger.apply_correction(
        correction(
            "SUPERSEDE",
            target_requirement_id="R1",
            new_requirement_id="R2",
            content="Export JSON",
        )
    )

    assert ledger.get("R1").current.status == "Superseded"
    assert ledger.get("R1").current.superseded_by == "R2"
    assert new.current.requirement_id == "R2"
    assert new.current.version == 1
    assert new.current.status == "Active"


def test_revoke_appends_revoked_version_without_erasing_history() -> None:
    ledger = RequirementLedger()
    ledger.add_requirement("R1", "Export XML", NOW)

    record = ledger.apply_correction(correction("REVOKE", target_requirement_id="R1"))

    assert len(record.versions) == 2
    assert record.versions[0].status == "Active"
    assert record.current.status == "Revoked"
    assert record.current.content == "Export XML"
    assert ledger.active_requirements() == []


@pytest.mark.parametrize(
    "item",
    [
        correction("AMEND", target_requirement_id="missing", content="new"),
        correction("REVOKE", target_requirement_id="missing"),
        correction("AMEND", target_requirement_id="R1"),
        correction("SUPERSEDE", target_requirement_id="R1", content="new"),
        correction("SUPERSEDE", target_requirement_id="R1", new_requirement_id="R2"),
        correction("ADD", new_requirement_id="R1"),
    ],
)
def test_invalid_corrections_raise_value_error(item: Correction) -> None:
    ledger = RequirementLedger()
    ledger.add_requirement("R1", "old", NOW)

    with pytest.raises(ValueError):
        ledger.apply_correction(item)


@pytest.mark.parametrize("kind", ["AMEND", "REVOKE", "SUPERSEDE"])
def test_inactive_requirement_cannot_be_modified_again(kind: str) -> None:
    ledger = RequirementLedger()
    ledger.add_requirement("R1", "old", NOW)
    ledger.apply_correction(correction("REVOKE", target_requirement_id="R1"))

    with pytest.raises(ValueError, match="active"):
        ledger.apply_correction(
            correction(
                kind,
                target_requirement_id="R1",
                content="new",
                new_requirement_id="R2" if kind == "SUPERSEDE" else None,
            )
        )


def test_duplicate_requirement_id_is_rejected() -> None:
    ledger = RequirementLedger()
    ledger.add_requirement("R1", "first", NOW)

    with pytest.raises(ValueError):
        ledger.add_requirement("R1", "second", NOW)


def test_json_round_trip_preserves_all_versions_and_statuses() -> None:
    ledger = RequirementLedger()
    ledger.add_requirement("R1", "Export XML", NOW)
    ledger.apply_correction(
        correction(
            "SUPERSEDE",
            target_requirement_id="R1",
            new_requirement_id="R2",
            content="Export JSON",
        )
    )
    ledger.apply_correction(correction("ADD", new_requirement_id="R3", content="Keep checksum"))

    restored = RequirementLedger.from_json(ledger.to_json())

    assert restored.to_json() == ledger.to_json()
    assert [item.requirement_id for item in restored.active_requirements()] == ["R2", "R3"]
    assert [item.requirement_id for item in restored.invalid_versions()] == ["R1"]
