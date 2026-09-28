"""AgentCore Platform v1.0"""

# OutputValidate — outer post_process node.
# S-3 deterministic output gate (preservation variant): every mismatches/exceptions
# entry in the rendered brief must carry source_refs already present in Reconcile's
# own reconciled result set (state["mismatches"] / state["exceptions"], merged from
# the inner subgraph). A claim with missing/unmatched source_refs is dropped (not
# silently suppressed — status flips to ERROR and error_log records what was dropped).

from typing import Any, ClassVar

from framework.nodes.function_node import FunctionNode
from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel
from shared.utils.audit_logger import emit_trace_event


def _known_source_refs(state: dict[str, Any]) -> set[str]:
    refs: set[str] = set()
    for entry in state.get("mismatches", []) or []:
        refs.update(entry.get("source_refs", []) or [])
    for entry in state.get("exceptions", []) or []:
        refs.update(entry.get("source_refs", []) or [])
    return refs


class OutputValidateNode(FunctionNode):
    """OutputValidate: S-3 citation-preservation gate on the rendered brief."""

    required_trust_level: ClassVar[TrustLevel] = TrustLevel.ANONYMOUS

    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        brief = state.get("brief") or {}
        known_refs = _known_source_refs(state)

        dropped: list[str] = []

        def _filter(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
            kept = []
            for entry in entries:
                refs = entry.get("source_refs") or []
                if refs and known_refs.issuperset(refs):
                    kept.append(entry)
                else:
                    dropped.append(str(entry.get("facility_id") or entry.get("type") or "unknown"))
            return kept

        validated_mismatches = _filter(list(brief.get("mismatches", []) or []))
        validated_exceptions = _filter(list(brief.get("exceptions", []) or []))

        validated_brief = {
            **brief,
            "mismatches": validated_mismatches,
            "exceptions": validated_exceptions,
        }

        emit_trace_event(
            "output_validated",
            {
                "correlation_id": state.get("correlation_id"),
                "kept_mismatches": len(validated_mismatches),
                "kept_exceptions": len(validated_exceptions),
                "dropped_count": len(dropped),
            },
            state,
        )

        if dropped:
            return {
                "brief": validated_brief,
                "formatted_output": validated_brief,
                "status": AgentStatus.ERROR.value,
                "error_log": [f"OutputValidate: dropped {len(dropped)} uncited claim(s): {dropped}"],
            }

        return {
            "brief": validated_brief,
            "formatted_output": validated_brief,
            "status": AgentStatus.SUCCESS.value,
        }

    def _extra_security_gate_output(self, state: dict[str, Any]) -> dict[str, Any]:
        # S-3 preservation-variant re-check: verify this node's OWN output key
        # (formatted_output) is still an internally-consistent dict — never
        # re-derive from upstream/input fields. Non-raising; always returns dict.
        formatted = state.get("formatted_output")
        if formatted is not None and not isinstance(formatted, dict):
            return {
                **state,
                "status": AgentStatus.ERROR.value,
                "error_log": [*state.get("error_log", []), "OutputValidate: formatted_output must be a dict"],
            }
        return state
