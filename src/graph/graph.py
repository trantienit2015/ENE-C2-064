"""AgentCore Platform v1.0"""

# ENE-C2-064 — Renewable Energy Certificate Evidence Reconciliation Brief
#
# Cat 2 — outer AgentBaseGraph + GraphNode in the `main` slot wrapping an inner
# BaseGraph (domain workflow). Backbone (fixed, same as Cat 1):
#   START -> initialize -> pre_process(InputValidate) -> main(ReconcileGraphNode)
#         -> post_process(OutputValidate) -> finalize -> END
#
# Inside `main` (ReconcileGraphNode.execute()): GraphNode calls the inner
# CertificateReconciliationWorkflowGraph.invoke(user_input, ctx=ctx), which runs
# EvidenceExtract -> Reconcile -> BriefRender. merge_output() maps sub_result
# fields back into the outer state.
#
# ReconcileGraphNode is defined in THIS file (not src/nodes/) because
# tests/proof_of_boundary/test_pb_invoke_order.py
# auto-discovers every BaseNode subclass under src/nodes/ and asserts the
# standard S-1->S-4->S-2->execute->S-3->S-4 lifecycle, which GraphNode does not
# follow (it delegates security gating to the inner subgraph).

from typing import Any, ClassVar, cast

from framework.graph.agent_base_graph import AgentBaseGraph
from framework.nodes.graph_node import GraphNode
from framework.schemas.agent_state import AgentState
from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel
from shared.utils.audit_logger import emit_trace_event

from src.nodes.input_validate_node import InputValidateNode
from src.nodes.output_validate_node import OutputValidateNode
from src.schemas.state import State


class ReconcileGraphNode(GraphNode):
    """Wraps the inner certificate-reconciliation workflow; assigned to `main`."""

    # S-1: outer main-slot wrapper — first node in the outer backbone
    # to receive dispatched caller input; must match agent.yaml required_trust_level
    # and sibling outer nodes (InputValidate/OutputValidate).
    required_trust_level: ClassVar[TrustLevel] = TrustLevel.VERIFIED_EXTERNAL
    error_strategy: ClassVar[str] = "propagate"
    propagate_hitl: ClassVar[bool] = False

    def __init__(self, llm: Any = None) -> None:
        super().__init__()
        self._llm = llm

    def get_subgraph(self) -> Any:
        from src.graph.domain_workflow_graph import CertificateReconciliationWorkflowGraph

        sg = CertificateReconciliationWorkflowGraph(config=self._parent_config())
        sg.compile()
        return sg

    def extract_input(self, state: AgentState) -> str:
        # S-4: runs inside GraphNode.execute() — audit the dispatch into the inner subgraph.
        emit_trace_event(
            "reconciliation_dispatched",
            {"correlation_id": state.get("correlation_id")},
            state,
        )
        # Re-validate the pre_process precondition here: the outer pre_process ->
        # main edge is unconditional (AgentBaseGraph.add_edges), so a failed
        # InputValidate (e.g. S-1 trust denial) does NOT stop main from running.
        # If pre_process did not succeed, refuse to dispatch raw/unvalidated
        # input into the inner subgraph — return "" so EvidenceExtractNode's own
        # JSON guard fails closed instead of silently reconciling unvalidated data.
        if state.get("status") not in (AgentStatus.SUCCESS.value, AgentStatus.SUCCESS.value):
            return ""
        return cast(str, state.get("validated_input", state.get("user_input", "")))

    def merge_output(self, state: AgentState, sub_result: dict[str, Any]) -> dict[str, Any]:
        # S-4: runs inside GraphNode.execute() — audit the subgraph outcome merged back out.
        emit_trace_event(
            "reconciliation_completed_outer",
            {
                "correlation_id": state.get("correlation_id"),
                "mismatch_count": len(sub_result.get("mismatches", []) or []),
                "exception_count": len(sub_result.get("exceptions", []) or []),
            },
            state,
        )
        return {
            "mismatches": sub_result.get("mismatches", []),
            "exceptions": sub_result.get("exceptions", []),
            "reconciled_records": sub_result.get("reconciled_records", []),
            "brief": sub_result.get("brief"),
            "status": sub_result.get("status"),
        }

    def _parent_config(self) -> dict[str, Any]:
        return {"llm": self._llm}


class CertificateReconciliationGraph(AgentBaseGraph):
    """ENE-C2-064 outer graph — L1 direct (AgentBaseGraph)."""

    @property
    def name(self) -> str:
        return "ene-c2-064"

    @property
    def state_schema(self) -> type:
        return State

    def register_nodes(self) -> None:
        super().register_nodes()  # injects InitializeNode + FinalizeNode
        llm = self.config.get("llm")
        self._nodes["pre_process"] = InputValidateNode()
        self._nodes["main"] = ReconcileGraphNode(llm=llm)
        self._nodes["post_process"] = OutputValidateNode()

    # add_edges() is NOT overridden — backbone wiring belongs to the framework.


Graph = CertificateReconciliationGraph  # alias for agent.yaml module:"src.graph"
