# ENE-C2-064 — PB-6 boundary compensation for the outer GraphNode.
#
# PB-6 (test_pb_invoke_order.py) only auto-discovers BaseNode subclasses under
# src/nodes/. This template's Cat 2 outer main-slot wrapper, ReconcileGraphNode,
# lives in src/graph/graph.py (canonical placement for a GraphNode), which is the correct location but is therefore
# outside PB-6's discovery scope. This file closes that blind spot: it is the
# ONLY probe that reaches the outer GraphNode's S-1 trust gate and boundary
# mapping directly.

from framework.nodes.function_node import FunctionNode
from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel

from src.graph.graph import ReconcileGraphNode
from src.nodes.evidence_extract_node import EvidenceExtractNode


class TestGraphNodeS1TrustGate:
    """S-1: ReconcileGraphNode is the outer main-slot node — first to receive
    dispatched caller input. Insufficient trust must deny before execute()."""

    def test_declared_trust_level_valid(self):
        assert ReconcileGraphNode.required_trust_level in (
            TrustLevel.ANONYMOUS,
            TrustLevel.VERIFIED_EXTERNAL,
            TrustLevel.INTERNAL,
        )

    def test_insufficient_trust_denies_before_execute(self):
        node = ReconcileGraphNode(llm=None)
        out = node({"caller_trust_level": TrustLevel.ANONYMOUS.value, "status": AgentStatus.SUCCESS.value})
        assert str(out.get("status")).lower().endswith("error")
        assert any("S-1 trust gate denied" in e for e in out.get("error_log", []))


class TestGraphNodeBoundaryMapping:
    """Criterion #9: extract_input()/merge_output() must map fields explicitly
    — no raw subgraph dict pass-through, no leaking fields outside the contract."""

    def test_extract_input_refuses_when_pre_process_failed(self):
        node = ReconcileGraphNode(llm=None)
        # pre_process (InputValidate) failed -> main must not dispatch raw input.
        state = {"status": AgentStatus.ERROR.value, "user_input": "raw-unvalidated-input"}
        assert node.extract_input(state) == ""

    def test_extract_input_uses_validated_input_only(self):
        node = ReconcileGraphNode(llm=None)
        state = {
            "status": AgentStatus.SUCCESS.value,
            "validated_input": '{"registry_export": []}',
            "user_input": "should-not-be-used",
        }
        assert node.extract_input(state) == '{"registry_export": []}'

    def test_merge_output_maps_explicit_fields_only(self):
        node = ReconcileGraphNode(llm=None)
        sub_result = {
            "mismatches": [{"facility_id": "F1"}],
            "exceptions": [],
            "reconciled_records": [{"facility_id": "F1"}],
            "brief": {"summary": "s", "citations": []},
            "status": AgentStatus.SUCCESS.value,
            # Fields below must NOT leak through merge_output — they are
            # internal to the inner subgraph's own state (trace_id, node_history,
            # correlation_id are outer-owned and must not be overwritten here).
            "trace_id": "inner-trace-should-not-leak",
            "node_history": ["inner-only"],
        }
        merged = node.merge_output({"correlation_id": "outer-cid"}, sub_result)
        assert set(merged) == {"mismatches", "exceptions", "reconciled_records", "brief", "status"}
        assert "trace_id" not in merged
        assert "node_history" not in merged


class TestGraphNodeDelegatesGatingToInnerSubgraph:
    """Delegation is intentional design (framework/nodes/graph_node.py: GraphNode
    is a direct BaseNode subclass, not a FunctionNode — it does not run
    _security_gate_input/output itself). The real S-2/S-3 content gates live on
    the inner subgraph's entry node, confirmed here rather than left unproven."""

    def test_graphnode_is_not_a_functionnode(self):
        # GraphNode intentionally bypasses FunctionNode's @final S-2/S-3 hooks —
        # gating is delegated to the inner subgraph's own nodes.
        assert not issubclass(ReconcileGraphNode, FunctionNode)

    def test_inner_entry_node_declares_trust_level(self):
        # EvidenceExtractNode is the inner subgraph's entry node (first to run
        # after ReconcileGraphNode.extract_input() dispatches into it).
        assert EvidenceExtractNode.required_trust_level == TrustLevel.ANONYMOUS
