"""AgentCore Platform v1.0"""

# ENE-C2-064 — inner certificate-reconciliation workflow.
# Called by ReconcileGraphNode.get_subgraph() in src/graph/graph.py.
# Pipeline: START -> evidence_extract -> reconcile -> brief_render -> END.

from typing import Any
from langgraph.graph import END, START

from framework.graph.base_graph import BaseGraph
from framework.schemas.agent_state import AgentState
from framework.schemas.agent_status import AgentStatus

from src.nodes.brief_render_node import BriefRenderNode
from src.nodes.evidence_extract_node import EvidenceExtractNode
from src.nodes.reconcile_node import ReconcileNode
from src.schemas.state import State


class CertificateReconciliationWorkflowGraph(BaseGraph):
    """Inner graph: EvidenceExtract -> Reconcile -> BriefRender."""

    @property
    def name(self) -> str:
        return "certificate_reconciliation_workflow"

    @property
    def state_schema(self) -> type:
        return State

    def _validate_config(self) -> None:
        pass

    def register_nodes(self) -> None:
        # No super() call — BaseGraph.register_nodes() is abstract.
        llm = self.config.get("llm") if hasattr(self, "config") else None
        self._nodes["evidence_extract"] = EvidenceExtractNode(llm=llm)
        self._nodes["reconcile"] = ReconcileNode()
        self._nodes["brief_render"] = BriefRenderNode(llm=llm)

    def add_edges(self) -> None:
        self._sg.add_edge(START, "evidence_extract")
        self._sg.add_edge("evidence_extract", "reconcile")
        self._sg.add_edge("reconcile", "brief_render")
        self._sg.add_edge("brief_render", END)

    def route(self, state: AgentState) -> str:
        # Required by ABC; this topology is linear (never invoked via
        # add_conditional_edges), but must be implemented.
        return END if state.get("status") == AgentStatus.ERROR.value else "brief_render"

    def get_output(self, state: AgentState) -> dict[str, Any]:
        return {
            "mismatches": state.get("mismatches", []),
            "exceptions": state.get("exceptions", []),
            "reconciled_records": state.get("reconciled_records", []),
            "brief": state.get("brief"),
            "status": state.get("status"),
            "trace_id": state.get("trace_id"),
            "correlation_id": state.get("correlation_id"),
            "node_history": state.get("node_history", []),
        }
