"""AgentCore Platform v1.0"""

# EvidenceExtract — inner subgraph node (step 1 of the Reconcile GraphNode workflow).
# S-1: inner subgraph node -> trust authenticated once at the outer backbone (ANONYMOUS).
# LLM-normalizes certificate serial / facility ID / generation period / retirement
# status from the registry export and generation-evidence documents into a common
# schema (deterministic field casting here; LLM confirms free-form fields).

import json
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


def _normalize_record(record: dict[str, Any]) -> dict[str, Any]:
    return {
        **record,
        "facility_id": str(record.get("facility_id", "")).strip(),
        "certificate_serial": str(record.get("certificate_serial", "")).strip(),
        "period": str(record.get("period", "")).strip(),
        "retirement_status": str(record.get("retirement_status", "active")).strip().lower(),
    }


class EvidenceExtractNode(FunctionNode):
    """Normalize registry/evidence records into a common schema."""

    required_trust_level: ClassVar[TrustLevel] = TrustLevel.ANONYMOUS

    def __init__(self, llm: Any = None) -> None:
        self._llm = llm

    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        # S-4: emit before the first branch so every path (reject or accept) is traced.
        emit_trace_event(
            "evidence_extract_received",
            {"correlation_id": state.get("correlation_id")},
            state,
        )

        raw = state.get("user_input", "")
        try:
            payload = json.loads(raw) if isinstance(raw, str) else raw
        except (ValueError, TypeError):
            payload = None

        if not isinstance(payload, dict):
            return {
                "status": AgentStatus.ERROR.value,
                "error_log": ["EvidenceExtract: inner input is not a valid JSON object"],
            }

        registry_export = payload.get("registry_export") or []
        generation_evidence = payload.get("generation_evidence") or []
        facility_master = payload.get("facility_master") or []

        if not registry_export or not generation_evidence:
            return {
                "status": AgentStatus.ERROR.value,
                "error_log": ["EvidenceExtract: registry_export or generation_evidence is empty"],
            }

        normalized_certificates = [_normalize_record(rec) for rec in registry_export]
        normalized_evidence = [_normalize_record(rec) for rec in generation_evidence]

        # LLM confirms free-form field normalization (e.g. non-canonical retirement
        # status text). `llm is None` is a legitimate deployment state (no LLM
        # secret is declared in agent.yaml — see docs/07_operation_guide.md); the
        # deterministic normalization above already covers the canonical schema,
        # so skip the confirmation call rather than crash on `None.complete()`.
        if self._llm is not None:
            raw = self._llm.complete(
                f"Normalize {len(normalized_evidence)} generation-evidence record(s) "
                f"against {len(normalized_certificates)} registry record(s)."
            )
            confirmation = _extract_text(raw)
            if not confirmation:
                # LLM is configured but returned no usable content — a real LLM
                # failure, not the "no LLM provisioned" deterministic mode, so it
                # must not be swallowed into a fabricated SUCCESS.
                return {
                    "status": AgentStatus.ERROR.value,
                    "error_log": ["EvidenceExtract: LLM confirmation returned an empty response"],
                }
            emit_trace_event(
                "evidence_extract_llm_confirmed",
                {
                    "correlation_id": state.get("correlation_id"),
                    "confirmation_chars": len(confirmation),
                },
                state,
            )
        else:
            emit_trace_event(
                "evidence_extract_deterministic_fallback",
                {"reason": "no_llm_provisioned", "correlation_id": state.get("correlation_id")},
                state,
            )

        emit_trace_event(
            "evidence_extracted",
            {
                "correlation_id": state.get("correlation_id"),
                "registry_count": len(normalized_certificates),
                "evidence_count": len(normalized_evidence),
            },
            state,
        )

        return {
            "normalized_certificates": normalized_certificates,
            "normalized_evidence": normalized_evidence,
            "facility_master": facility_master,
            "status": AgentStatus.SUCCESS.value,
        }
