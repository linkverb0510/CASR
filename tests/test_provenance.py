from __future__ import annotations

from datetime import datetime, timezone
import json

import pytest

from casr.models import Action, Artifact, Evidence, RequirementVersion
from casr.provenance import ProvenanceGraph

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def requirement(requirement_id: str = "R1", version: int = 1) -> RequirementVersion:
    return RequirementVersion(
        requirement_id=requirement_id,
        version=version,
        content="Export JSON",
        status="Active",
        created_at=NOW,
    )


def action(action_id: str = "A1") -> Action:
    return Action(
        action_id=action_id,
        action_type="edit",
        description="Write exporter",
        timestamp=NOW,
    )


def artifact(artifact_id: str = "F1") -> Artifact:
    return Artifact(artifact_id=artifact_id, path=f"src/{artifact_id}.py")


def evidence() -> Evidence:
    return Evidence(
        evidence_id="E1",
        evidence_type="test",
        command=["python", "-m", "unittest"],
        status="PASS",
        timestamp=NOW,
    )


def test_node_ids_are_stable_and_duplicate_nodes_update_data() -> None:
    graph = ProvenanceGraph()
    assert graph.add_requirement_version(requirement()) == "requirement:R1:v1"
    assert graph.add_action(action()) == "action:A1"
    assert graph.add_artifact(artifact()) == "artifact:F1"
    assert graph.add_evidence(evidence()) == "evidence:E1"

    updated = requirement().model_copy(update={"content": "Export JSON safely"})
    graph.add_requirement_version(updated)
    payload = graph.to_dict()
    assert len(payload["nodes"]) == 4
    requirement_node = next(
        node for node in payload["nodes"] if node["id"] == "requirement:R1:v1"
    )
    assert requirement_node["data"]["content"] == "Export JSON safely"


def test_rejects_unknown_nodes_and_invalid_relations() -> None:
    graph = ProvenanceGraph()
    graph.add_requirement_version(requirement())
    graph.add_action(action())
    graph.add_artifact(artifact())
    graph.add_evidence(evidence())

    with pytest.raises(ValueError, match="unknown"):
        graph.add_relation(
            "action:missing", "artifact:F1", "Produces", "manual", 1.0, True
        )
    with pytest.raises(ValueError, match="not allowed"):
        graph.add_relation(
            "action:A1", "requirement:R1:v1", "Produces", "manual", 1.0, True
        )
    with pytest.raises(ValueError, match="not allowed"):
        graph.add_relation(
            "artifact:F1", "artifact:F1", "Motivates", "manual", 1.0, True
        )


@pytest.mark.parametrize("confidence", [-0.01, 1.01, float("nan")])
def test_rejects_invalid_confidence(confidence: float) -> None:
    graph = ProvenanceGraph()
    graph.add_requirement_version(requirement())
    graph.add_action(action())
    with pytest.raises(ValueError, match="confidence"):
        graph.add_relation(
            "requirement:R1:v1",
            "action:A1",
            "Motivates",
            "manual",
            confidence,
            True,
        )


def test_all_relation_directions_and_json_round_trip() -> None:
    graph = ProvenanceGraph()
    graph.add_requirement_version(requirement())
    graph.add_action(action())
    graph.add_artifact(artifact("F1"))
    graph.add_artifact(artifact("F2"))
    graph.add_evidence(evidence())
    graph.add_relation("requirement:R1:v1", "action:A1", "Motivates", "manual", 0.9, True)
    graph.add_relation("action:A1", "artifact:F1", "Produces", "git", 1.0, False)
    graph.add_relation("artifact:F2", "artifact:F1", "Depends-on", "test", 0.8, False)
    graph.add_relation("evidence:E1", "requirement:R1:v1", "Validates", "test", 1.0, False)

    payload = json.loads(json.dumps(graph.to_dict(), ensure_ascii=False))
    restored = ProvenanceGraph.from_dict(payload)
    assert restored.to_dict() == graph.to_dict()
    assert restored.impact_edges() == graph.impact_edges()


def test_from_dict_rejects_non_boolean_human_verified() -> None:
    graph = ProvenanceGraph()
    graph.add_action(action())
    graph.add_artifact(artifact("F1"))
    graph.add_relation("action:A1", "artifact:F1", "Produces", "llm", 0.99, False)
    payload = json.loads(json.dumps(graph.to_dict()))
    payload["edges"][0]["human_verified"] = "false"

    with pytest.raises(ValueError, match="human_verified"):
        ProvenanceGraph.from_dict(payload)


def test_from_dict_rejects_tampered_impact_eligibility() -> None:
    graph = ProvenanceGraph()
    graph.add_action(action())
    graph.add_artifact(artifact("F1"))
    graph.add_relation("action:A1", "artifact:F1", "Produces", "llm", 0.99, False)
    payload = json.loads(json.dumps(graph.to_dict()))
    payload["edges"][0]["impact_eligible"] = True

    with pytest.raises(ValueError, match="impact_eligible"):
        ProvenanceGraph.from_dict(payload)


def test_from_dict_validates_node_schema_and_identity() -> None:
    graph = ProvenanceGraph()
    graph.add_action(action())
    payload = json.loads(json.dumps(graph.to_dict()))
    payload["nodes"][0]["data"]["action_type"] = 123

    with pytest.raises(ValueError):
        ProvenanceGraph.from_dict(payload)


def test_unverified_llm_edges_are_preserved_but_not_impact_eligible() -> None:
    graph = ProvenanceGraph()
    graph.add_action(action())
    graph.add_artifact(artifact("F1"))
    graph.add_artifact(artifact("F2"))
    graph.add_relation("action:A1", "artifact:F1", "Produces", "manual", 1.0, True)
    graph.add_relation("action:A1", "artifact:F2", "Produces", "llm", 0.99, False)

    assert ("action:A1", "artifact:F2") in {
        (edge["source"], edge["target"]) for edge in graph.to_dict()["edges"]
    }
    assert {target for _, target, _ in graph.impact_edges()} == {"artifact:F1"}

    graph.add_relation("action:A1", "artifact:F2", "Produces", "llm", 0.99, True)
    assert {target for _, target, _ in graph.impact_edges()} == {
        "artifact:F1",
        "artifact:F2",
    }
