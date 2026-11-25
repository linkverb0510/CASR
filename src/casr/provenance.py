from __future__ import annotations

import math
from typing import Literal, cast

import networkx as nx

from casr.models import Action, Artifact, Evidence, RequirementVersion

RelationType = Literal["Motivates", "Produces", "Depends-on", "Validates"]
RelationSource = Literal["git", "test", "manual", "llm"]

_ALLOWED_RELATIONS: dict[str, tuple[set[str], set[str]]] = {
    "Motivates": ({"requirement"}, {"action"}),
    "Produces": ({"action"}, {"artifact"}),
    "Depends-on": ({"artifact"}, {"artifact"}),
    "Validates": ({"evidence"}, {"requirement", "artifact"}),
}


class ProvenanceGraph:
    def __init__(self) -> None:
        self._graph: nx.DiGraph = nx.DiGraph()

    @staticmethod
    def _node_id(kind: str, item_id: str, version: int | None = None) -> str:
        if kind == "requirement":
            return f"requirement:{item_id}:v{version}"
        return f"{kind}:{item_id}"

    def _add_node(self, node_id: str, kind: str, data: dict[str, object]) -> str:
        if node_id in self._graph and self._graph.nodes[node_id]["kind"] != kind:
            raise ValueError(f"node id already exists with a different kind: {node_id}")
        self._graph.add_node(node_id, kind=kind, data=data)
        return node_id

    def add_requirement_version(self, version: RequirementVersion) -> str:
        return self._add_node(
            self._node_id("requirement", version.requirement_id, version.version),
            "requirement",
            version.model_dump(mode="json"),
        )

    def add_action(self, action: Action) -> str:
        return self._add_node(
            self._node_id("action", action.action_id),
            "action",
            action.model_dump(mode="json"),
        )

    def add_artifact(self, artifact: Artifact) -> str:
        return self._add_node(
            self._node_id("artifact", artifact.artifact_id),
            "artifact",
            artifact.model_dump(mode="json"),
        )

    def add_evidence(self, evidence: Evidence) -> str:
        return self._add_node(
            self._node_id("evidence", evidence.evidence_id),
            "evidence",
            evidence.model_dump(mode="json"),
        )

    def add_relation(
        self,
        source_id: str,
        target_id: str,
        relation: RelationType,
        source: RelationSource,
        confidence: float,
        human_verified: bool,
    ) -> None:
        if source_id not in self._graph or target_id not in self._graph:
            raise ValueError("relation references an unknown node")
        if not isinstance(relation, str) or relation not in _ALLOWED_RELATIONS:
            raise ValueError(f"unknown relation: {relation}")
        if not isinstance(source, str) or source not in {"git", "test", "manual", "llm"}:
            raise ValueError(f"unknown relation source: {source}")
        if type(human_verified) is not bool:
            raise ValueError("human_verified must be a boolean")
        if type(confidence) not in {int, float} or not math.isfinite(confidence) or not 0 <= confidence <= 1:
            raise ValueError("confidence must be within [0, 1]")
        source_kinds, target_kinds = _ALLOWED_RELATIONS[relation]
        if (
            self._graph.nodes[source_id]["kind"] not in source_kinds
            or self._graph.nodes[target_id]["kind"] not in target_kinds
        ):
            raise ValueError(f"relation {relation} is not allowed for these node kinds")
        self._graph.add_edge(
            source_id,
            target_id,
            relation=relation,
            relation_source=source,
            confidence=confidence,
            human_verified=human_verified,
            impact_eligible=source != "llm" or human_verified,
        )

    def impact_edges(self) -> list[tuple[str, str, dict[str, object]]]:
        return [
            (source, target, dict(data))
            for source, target, data in sorted(self._graph.edges(data=True))
            if data["impact_eligible"]
        ]

    def to_dict(self) -> dict[str, object]:
        nodes = [
            {"id": node_id, "kind": data["kind"], "data": data["data"]}
            for node_id, data in sorted(self._graph.nodes(data=True))
        ]
        edges = [
            {
                "source": source,
                "target": target,
                "relation": data["relation"],
                "relation_source": data["relation_source"],
                "confidence": data["confidence"],
                "human_verified": data["human_verified"],
                "impact_eligible": data["impact_eligible"],
            }
            for source, target, data in sorted(self._graph.edges(data=True))
        ]
        return {"nodes": nodes, "edges": edges}

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> ProvenanceGraph:
        graph = cls()
        nodes = payload.get("nodes")
        edges = payload.get("edges")
        if not isinstance(nodes, list) or not isinstance(edges, list):
            raise ValueError("graph payload requires nodes and edges lists")
        validators = {
            "requirement": (RequirementVersion, graph.add_requirement_version),
            "action": (Action, graph.add_action),
            "artifact": (Artifact, graph.add_artifact),
            "evidence": (Evidence, graph.add_evidence),
        }
        for item in nodes:
            if not isinstance(item, dict):
                raise ValueError("invalid graph node")
            node_id = item.get("id")
            kind = item.get("kind")
            data = item.get("data")
            if not isinstance(node_id, str) or not isinstance(kind, str) or not isinstance(data, dict):
                raise ValueError("invalid graph node")
            if kind not in validators:
                raise ValueError(f"unknown graph node kind: {kind}")
            model, add_node = validators[kind]
            validated = model.model_validate(data)
            if add_node(validated) != node_id:
                raise ValueError(f"graph node id does not match its data: {node_id}")
        for item in edges:
            if not isinstance(item, dict):
                raise ValueError("invalid graph edge")
            human_verified = item.get("human_verified")
            relation_source = item.get("relation_source")
            if type(human_verified) is not bool:
                raise ValueError("human_verified must be a boolean")
            if not isinstance(relation_source, str):
                raise ValueError("unknown relation source")
            expected_eligible = relation_source != "llm" or human_verified
            if "impact_eligible" in item and item["impact_eligible"] is not expected_eligible:
                raise ValueError("impact_eligible does not match relation provenance")
            graph.add_relation(
                cast(str, item.get("source")),
                cast(str, item.get("target")),
                cast(RelationType, item.get("relation")),
                cast(RelationSource, relation_source),
                cast(float, item.get("confidence")),
                human_verified,
            )
        return graph
