"""AgentCore Platform v1.0"""

# BriefRender — inner subgraph node (step 3). LLM assembles the reconciled findings
# into a structured, cited human-review brief — every claim references a
# source_refs record ID produced by Reconcile (step 2); BriefRender does not
# introduce claims without a source_refs, and OutputValidate (outer post_process,
# S-3 preservation gate) drops any that slip through.
# S-1: inner subgraph node -> ANONYMOUS (trust authenticated once at outer backbone).

from typing import Any, ClassVar

from framework.nodes.function_node import FunctionNode
from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel
from shared.utils.audit_logger import emit_trace_event


def _extract_text(raw: Any) -> str:
    # Canonical BaseLLM.complete() -> {"content": str, ...}; some test fakes still
    # return a bare string. Never treat the raw dict as a string downstream.
    if isinstance(raw, dict):
        content = raw.get("content", "")
        return content if isinstance(content, str) else ""
    if isinstance(raw, str):
        return raw
    return ""


class BriefRenderNode(FunctionNode):
    """Render a cited human-review brief from reconciled mismatches/exceptions."""

    required_trust_level: ClassVar[TrustLevel] = TrustLevel.ANONYMOUS

    def __init__(self, llm: Any = None) -> None:
        self._llm = llm

    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        # S-4: emit before the first branch so every path (reject or accept) is traced.
        emit_trace_event(
            "brief_render_received",
            {"correlation_id": state.get("correlation_id")},
            state,
        )

        mismatches = state.get("mismatches")
        exceptions = state.get("exceptions")

        if mismatches is None or exceptions is None:
            return {
                "status": AgentStatus.ERROR.value,
                "error_log": ["BriefRender: no reconciliation result to render"],
            }

        # `llm is None` is a legitimate deployment state (no LLM secret declared
        # in agent.yaml — see docs/07_operation_guide.md): fall back to a
        # deterministic summary built from the reconciled counts instead of
        # crashing on `None.complete()`.
        if self._llm is not None:
            raw = self._llm.complete(
                f"Summarize {len(mismatches)} mismatch(es) and {len(exceptions)} exception(s) "
                "for a compliance reviewer. Do not retire certificates, make market claims, "
                "or attest compliance — this is a review aid only."
            )
            summary = _extract_text(raw)
            if not summary:
                # LLM is configured but returned no usable content — this is a real
                # LLM failure, not the "no LLM provisioned" deterministic mode, so it
                # must not be swallowed into a fabricated SUCCESS.
                return {
                    "status": AgentStatus.ERROR.value,
                    "error_log": ["BriefRender: LLM returned an empty response"],
                }
        else:
            summary = (
                f"{len(mismatches)} mismatch(es) and {len(exceptions)} exception(s) found "
                "across the reconciled certificate records. Review the cited entries below "
                "before taking any compliance action."
            )
            emit_trace_event(
                "brief_render_deterministic_fallback",
                {"reason": "no_llm_provisioned", "correlation_id": state.get("correlation_id")},
                state,
            )

        all_refs = sorted(
            {ref for entry in mismatches for ref in entry.get("source_refs", [])}
            | {ref for entry in exceptions for ref in entry.get("source_refs", [])}
        )

        brief = {
            "mismatches": mismatches,
            "exceptions": exceptions,
            "brief": {
                "summary": summary,
                "citations": all_refs,
            },
        }

        emit_trace_event(
            "brief_rendered",
            {
                "correlation_id": state.get("correlation_id"),
                "mismatch_count": len(mismatches),
                "exception_count": len(exceptions),
                "citation_count": len(all_refs),
            },
            state,
        )

        return {
            "brief": brief,
            "status": AgentStatus.SUCCESS.value,
        }
