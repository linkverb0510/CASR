from __future__ import annotations

from datetime import datetime, timezone

from casr.ledger import RequirementLedger
from casr.models import Action, Artifact, Correction, RequirementVersion
from casr.provenance import ProvenanceGraph
from casr.repair import RepairPlanner, analyze_impact

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def add_requirement(graph: ProvenanceGraph, requirement_id: str) -> None:
    graph.add_requirement_version(
        RequirementVersion(
            requirement_id=requirement_id,
            version=1,
            content=requirement_id,
            status="Active",
            created_at=NOW,
        )
    )


def add_action(graph: ProvenanceGraph, action_id: str) -> None:
    graph.add_action(
        Action(
            action_id=action_id,
            action_type="edit",
            description=action_id,
            timestamp=NOW,
        )
    )


def add_artifact(
    graph: ProvenanceGraph,
    artifact_id: str,
    baseline_blob: str | None = "base",
    current_blob: str | None = "current",
) -> None:
    graph.add_artifact(
        Artifact(
            artifact_id=artifact_id,
            path=f"src/{artifact_id}.py",
            baseline_blob=baseline_blob,
            current_blob=current_blob,
        )
    )


def build_graph() -> ProvenanceGraph:
    graph = ProvenanceGraph()
    for requirement_id in ["R-old", "R-keep"]:
        add_requirement(graph, requirement_id)
    for action_id in ["A-old", "A-keep"]:
        add_action(graph, action_id)
    for artifact_id in ["xml_helper", "exporter", "checksum", "cli", "unrelated"]:
        add_artifact(graph, artifact_id)
    graph.add_relation("requirement:R-old:v1", "action:A-old", "Motivates", "manual", 1.0, True)
    graph.add_relation("action:A-old", "artifact:xml_helper", "Produces", "git", 1.0, False)
    graph.add_relation("action:A-old", "artifact:exporter", "Produces", "git", 1.0, False)
    graph.add_relation("requirement:R-keep:v1", "action:A-keep", "Motivates", "manual", 1.0, True)
    graph.add_relation("action:A-keep", "artifact:exporter", "Produces", "git", 1.0, False)
    graph.add_relation("action:A-keep", "artifact:checksum", "Produces", "git", 1.0, False)
    graph.add_relation("artifact:cli", "artifact:exporter", "Depends-on", "test", 1.0, False)
    graph.add_relation("artifact:unrelated", "artifact:checksum", "Depends-on", "test", 1.0, False)
    graph.add_relation("artifact:unrelated", "artifact:xml_helper", "Depends-on", "llm", 0.99, False)
    return graph


def build_ledger() -> tuple[RequirementLedger, Correction]:
    ledger = RequirementLedger()
    ledger.add_requirement("R-old", "Export XML", NOW)
    ledger.add_requirement("R-keep", "Keep checksum", NOW)
    correction = Correction(
        correction_id="C1",
        correction_type="SUPERSEDE",
        target_requirement_id="R-old",
        new_requirement_id="R-new",
        content="Export JSON",
        created_at=NOW,
    )
    ledger.apply_correction(correction)
    return ledger, correction


def test_impact_propagation_respects_shared_and_verified_edges() -> None:
    graph = build_graph()
    ledger, correction = build_ledger()
    analysis = analyze_impact(graph, ledger, correction)

    assert analysis.seed_artifacts == {"xml_helper", "exporter"}
    assert analysis.active_supported_artifacts == {"exporter", "checksum"}
    assert analysis.exclusive_invalid_artifacts == {"xml_helper"}
    assert analysis.shared_artifacts == {"exporter"}
    assert analysis.downstream_artifacts == {"cli"}
    assert analysis.unaffected_active_artifacts == {"checksum"}


def test_repair_classification_prioritizes_shared_artifacts() -> None:
    graph = build_graph()
    ledger, correction = build_ledger()
    analysis = analyze_impact(graph, ledger, correction)
    plan = RepairPlanner(correction.correction_id).plan(analysis, graph)
    decisions = {decision.artifact_id: decision for decision in plan.decisions}

    assert decisions["exporter"].kind == "Modify"
    assert decisions["xml_helper"].kind == "Revert"
    assert decisions["cli"].kind == "Revalidate"
    assert decisions["checksum"].kind == "Retain"
    assert "unrelated" not in decisions
    assert len(decisions) == len(plan.decisions)


def test_add_correction_does_not_invalidate_existing_artifacts() -> None:
    graph = build_graph()
    ledger = RequirementLedger()
    ledger.add_requirement("R-old", "Export XML", NOW)
    ledger.add_requirement("R-keep", "Keep checksum", NOW)
    correction = Correction(
        correction_id="C-add",
        correction_type="ADD",
        new_requirement_id="R-extra",
        content="Extra output",
        created_at=NOW,
    )
    ledger.apply_correction(correction)

    analysis = analyze_impact(graph, ledger, correction)

    assert analysis.seed_artifacts == set()
    assert analysis.unaffected_active_artifacts == {"xml_helper", "exporter", "checksum"}


def test_add_does_not_reseed_previously_revoked_requirements() -> None:
    graph = build_graph()
    ledger = RequirementLedger()
    ledger.add_requirement("R-old", "Export XML", NOW)
    ledger.add_requirement("R-keep", "Keep checksum", NOW)
    ledger.apply_correction(
        Correction(
            correction_id="C-revoke",
            correction_type="REVOKE",
            target_requirement_id="R-old",
            created_at=NOW,
        )
    )
    correction = Correction(
        correction_id="C-add",
        correction_type="ADD",
        new_requirement_id="R-extra",
        content="Extra output",
        created_at=NOW,
    )
    ledger.apply_correction(correction)

    analysis = analyze_impact(graph, ledger, correction)

    assert analysis.seed_artifacts == set()
    assert analysis.exclusive_invalid_artifacts == set()


def test_amend_only_marks_historical_version_artifacts_as_invalid() -> None:
    graph = ProvenanceGraph()
    add_requirement(graph, "R-old")
    graph.add_requirement_version(
        RequirementVersion(
            requirement_id="R-old",
            version=2,
            content="Export JSON",
            status="Active",
            created_at=NOW,
        )
    )
    add_action(graph, "A-old")
    add_artifact(graph, "exporter")
    graph.add_relation("requirement:R-old:v1", "action:A-old", "Motivates", "manual", 1.0, True)
    graph.add_relation("action:A-old", "artifact:exporter", "Produces", "git", 1.0, False)
    ledger = RequirementLedger()
    ledger.add_requirement("R-old", "Export XML", NOW)
    correction = Correction(
        correction_id="C-amend",
        correction_type="AMEND",
        target_requirement_id="R-old",
        content="Export JSON",
        created_at=NOW,
    )
    ledger.apply_correction(correction)

    analysis = analyze_impact(graph, ledger, correction)

    assert analysis.seed_artifacts == {"exporter"}
    assert analysis.active_supported_artifacts == set()
    assert analysis.exclusive_invalid_artifacts == {"exporter"}
    assert analysis.shared_artifacts == set()


def test_new_artifact_reverts_and_missing_metadata_revalidates() -> None:
    graph = ProvenanceGraph()
    add_requirement(graph, "R-old")
    add_action(graph, "A-old")
    add_artifact(graph, "new_file", baseline_blob=None, current_blob="blob")
    add_artifact(graph, "unknown_file", baseline_blob=None, current_blob=None)
    graph.add_relation("requirement:R-old:v1", "action:A-old", "Motivates", "manual", 1.0, True)
    graph.add_relation("action:A-old", "artifact:new_file", "Produces", "git", 1.0, False)
    graph.add_relation("action:A-old", "artifact:unknown_file", "Produces", "git", 1.0, False)
    ledger = RequirementLedger()
    ledger.add_requirement("R-old", "Old", NOW)
    correction = Correction(
        correction_id="C1",
        correction_type="REVOKE",
        target_requirement_id="R-old",
        created_at=NOW,
    )
    ledger.apply_correction(correction)
    plan = RepairPlanner("C1").plan(analyze_impact(graph, ledger, correction), graph)
    kinds = {decision.artifact_id: decision.kind for decision in plan.decisions}
    assert kinds == {"new_file": "Revert", "unknown_file": "Revalidate"}
