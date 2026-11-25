from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from casr.ledger import RequirementLedger
from casr.models import Correction
from casr.provenance import ProvenanceGraph

RepairKind = Literal["Revert", "Modify", "Revalidate", "Retain"]


class ImpactAnalysis(BaseModel):
    seed_artifacts: set[str]
    active_supported_artifacts: set[str]
    exclusive_invalid_artifacts: set[str]
    shared_artifacts: set[str]
    downstream_artifacts: set[str]
    unaffected_active_artifacts: set[str]


class RepairDecision(BaseModel):
    kind: RepairKind
    artifact_id: str
    reason: str


class RepairPlan(BaseModel):
    correction_id: str
    decisions: list[RepairDecision] = Field(default_factory=list)


def _supported_artifacts(
    requirement_nodes: set[str], edges: list[tuple[str, str, dict[str, object]]]
) -> set[str]:
    artifacts: set[str] = set()
    changed = True
    while changed:
        changed = False
        for source, target, data in edges:
            if source in requirement_nodes and data["relation"] == "Motivates":
                if target not in requirement_nodes:
                    requirement_nodes.add(target)
                    changed = True
            elif source in requirement_nodes and data["relation"] == "Produces":
                artifact_id = str(target).removeprefix("artifact:")
                if artifact_id not in artifacts:
                    artifacts.add(artifact_id)
                    changed = True
    return artifacts


def analyze_impact(
    graph: ProvenanceGraph, ledger: RequirementLedger, correction: Correction
) -> ImpactAnalysis:
    if correction.correction_type != "ADD":
        if ledger.get(correction.target_requirement_id).current.status == "Active":
            raise ValueError("correction target is still active")

    invalid_requirement_ids = {
        version.requirement_id for version in ledger.invalid_versions()
    }
    active_requirement_ids = {
        version.requirement_id for version in ledger.active_requirements()
    }
    requirement_nodes = {
        node["id"]
        for node in graph.to_dict()["nodes"]
        if node["kind"] == "requirement"
    }
    invalid_nodes = {
        node_id
        for node_id in requirement_nodes
        if any(
            node_id.startswith(f"requirement:{requirement_id}:v")
            for requirement_id in invalid_requirement_ids
        )
    }
    active_nodes = {
        node_id
        for node_id in requirement_nodes
        if any(
            node_id.startswith(f"requirement:{requirement_id}:v")
            for requirement_id in active_requirement_ids
        )
    }
    edges = graph.impact_edges()
    seeds = _supported_artifacts(set(invalid_nodes), edges)
    active_supported = _supported_artifacts(set(active_nodes), edges)

    downstream: set[str] = set()
    changed = True
    while changed:
        changed = False
        for source, target, data in edges:
            if data["relation"] != "Depends-on":
                continue
            if target.removeprefix("artifact:") in seeds | downstream:
                source_id = source.removeprefix("artifact:")
                if source_id not in seeds | downstream:
                    downstream.add(source_id)
                    changed = True

    return ImpactAnalysis(
        seed_artifacts=seeds,
        active_supported_artifacts=active_supported,
        exclusive_invalid_artifacts=seeds - active_supported,
        shared_artifacts=seeds & active_supported,
        downstream_artifacts=downstream - seeds,
        unaffected_active_artifacts=active_supported - seeds - downstream,
    )


class RepairPlanner:
    def __init__(self, correction_id: str) -> None:
        self.correction_id = correction_id

    def plan(
        self, analysis: ImpactAnalysis, graph: ProvenanceGraph
    ) -> RepairPlan:
        artifacts = {
            node["data"]["artifact_id"]: node["data"]
            for node in graph.to_dict()["nodes"]
            if node["kind"] == "artifact"
        }
        decisions: list[RepairDecision] = []
        for artifact_id in sorted(artifacts):
            data = artifacts[artifact_id]
            baseline = data.get("baseline_blob")
            current = data.get("current_blob")
            if artifact_id in analysis.shared_artifacts:
                decisions.append(
                    RepairDecision(
                        kind="Modify",
                        artifact_id=artifact_id,
                        reason="artifact supports both invalid and active requirements",
                    )
                )
            elif artifact_id in analysis.exclusive_invalid_artifacts:
                if baseline is not None or current is not None:
                    decisions.append(
                        RepairDecision(
                            kind="Revert",
                            artifact_id=artifact_id,
                            reason="artifact exclusively supports invalid requirements and has recovery metadata",
                        )
                    )
                else:
                    decisions.append(
                        RepairDecision(
                            kind="Revalidate",
                            artifact_id=artifact_id,
                            reason="invalid artifact lacks baseline and current blob metadata",
                        )
                    )
            elif artifact_id in analysis.downstream_artifacts:
                decisions.append(
                    RepairDecision(
                        kind="Revalidate",
                        artifact_id=artifact_id,
                        reason="artifact depends on an affected artifact",
                    )
                )
            elif artifact_id in analysis.unaffected_active_artifacts:
                decisions.append(
                    RepairDecision(
                        kind="Retain",
                        artifact_id=artifact_id,
                        reason="artifact supports active requirements outside the impact set",
                    )
                )
        return RepairPlan(correction_id=self.correction_id, decisions=decisions)
