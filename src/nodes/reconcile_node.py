"""AgentCore Platform v1.0"""

# Reconcile — inner subgraph node (step 2). FunctionNode invoking the deterministic
# matcher in src/services/service.py (the "shared/tools/"-style pure-function
# matcher): exact-match
# facility_id+period+certificate_serial across registry vs generation evidence vs
# facility master; flags duplicate serials and period gaps/overlaps.
# S-1: inner subgraph node -> ANONYMOUS (trust authenticated once at outer backbone).

from typing import Any, ClassVar

from framework.nodes.function_node import FunctionNode
from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel
from shared.utils.audit_logger import emit_trace_event

from src.services.service import reconcile_records


class ReconcileNode(FunctionNode):
    """Deterministic cross-source certificate reconciliation."""

    required_trust_level: ClassVar[TrustLevel] = TrustLevel.ANONYMOUS

    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        # S-4: emit before the first branch so every path (reject or accept) is traced.
        emit_trace_event(
            "reconcile_received",
            {"correlation_id": state.get("correlation_id")},
            state,
        )

        registry = state.get("normalized_certificates", [])
        evidence = state.get("normalized_evidence", [])
        facility_master = state.get("facility_master", [])

        if not registry or not evidence:
            return {
                "status": AgentStatus.ERROR.value,
                "error_log": ["Reconcile: no normalized registry/evidence records to reconcile"],
            }

        result = reconcile_records(registry, evidence, facility_master)

        emit_trace_event(
            "reconciliation_completed",
            {
                "correlation_id": state.get("correlation_id"),
                "mismatch_count": len(result["mismatches"]),
                "exception_count": len(result["exceptions"]),
            },
            state,
        )

        return {
            "mismatches": result["mismatches"],
            "exceptions": result["exceptions"],
            "reconciled_records": result["reconciled_records"],
            "status": AgentStatus.SUCCESS.value,
        }
