"""AgentCore Platform v1.0"""

# InputValidate — outer pre_process node.
# S-1: required_trust_level=VERIFIED_EXTERNAL (privileged: accepts caller-supplied
#      registry/evidence/facility-master data before reconciliation).
# S-2: deterministic credential/path-traversal scan (reject) + non-regulated PII
#      flag-and-redact (facility_master owner/contact name+email+phone) — not a
#      reject.

import json
import re
from typing import Any, ClassVar

from framework.nodes.function_node import FunctionNode
from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel
from shared.utils.audit_logger import emit_trace_event

_CREDENTIAL_PATTERNS = [
    re.compile(r"Bearer\s+[A-Za-z0-9._-]{10,}", re.IGNORECASE),
    re.compile(r"eyJ[A-Za-z0-9._-]{10,}"),  # JWT
    re.compile(r"AKIA[A-Z0-9]{16}"),  # AWS access key
    re.compile(r"sk-[A-Za-z0-9]{20,}"),  # generic API key
]
_PATH_TRAVERSAL_PATTERN = re.compile(r"\.\./|\.\.\\")
_EMAIL_PATTERN = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_PHONE_PATTERN = re.compile(r"\+?\d[\d\-\s]{7,}\d")


def _redact_pii(record: dict[str, Any]) -> dict[str, Any]:
    redacted = dict(record)
    for field in ("owner", "contact_name", "contact_email", "contact_phone", "email", "phone"):
        value = redacted.get(field)
        if isinstance(value, str) and (
            _EMAIL_PATTERN.search(value)
            or _PHONE_PATTERN.search(value)
            or field.startswith("contact")
            or field == "owner"
        ):
            redacted[field] = "***REDACTED***"
    return redacted


class InputValidateNode(FunctionNode):
    """InputValidate: S-1 trust gate + S-2 deterministic input scan."""

    required_trust_level: ClassVar[TrustLevel] = TrustLevel.VERIFIED_EXTERNAL

    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        user_input = state.get("user_input", "")

        # S-4: emit before the first branch so every path (reject or accept) is traced.
        emit_trace_event(
            "input_validate_received",
            {"correlation_id": state.get("correlation_id")},
            state,
        )

        if not user_input or not str(user_input).strip():
            return {
                "status": AgentStatus.ERROR.value,
                "error_log": ["InputValidate: user_input is empty or missing"],
            }

        for pattern in _CREDENTIAL_PATTERNS:
            if pattern.search(user_input):
                return {
                    "status": AgentStatus.ERROR.value,
                    "error_log": ["InputValidate: credential pattern detected in user_input — rejected"],
                }
        if _PATH_TRAVERSAL_PATTERN.search(user_input):
            return {
                "status": AgentStatus.ERROR.value,
                "error_log": ["InputValidate: path-traversal pattern detected in user_input — rejected"],
            }

        try:
            payload = json.loads(user_input)
        except (ValueError, TypeError):
            return {
                "status": AgentStatus.ERROR.value,
                "error_log": ["InputValidate: user_input is not valid JSON"],
            }

        registry_export = payload.get("registry_export") or []
        generation_evidence = payload.get("generation_evidence") or []
        facility_master_raw = payload.get("facility_master") or []

        if (
            not isinstance(registry_export, list)
            or not isinstance(generation_evidence, list)
            or not isinstance(facility_master_raw, list)
        ):
            return {
                "status": AgentStatus.ERROR.value,
                "error_log": ["InputValidate: registry_export/generation_evidence/facility_master must be lists"],
            }

        facility_master = [_redact_pii(rec) if isinstance(rec, dict) else rec for rec in facility_master_raw]

        validated_payload = {
            "registry_export": registry_export,
            "generation_evidence": generation_evidence,
            "facility_master": facility_master,
        }

        emit_trace_event(
            "input_validated",
            {
                "correlation_id": state.get("correlation_id"),
                "registry_count": len(registry_export),
                "evidence_count": len(generation_evidence),
                "facility_count": len(facility_master),
            },
            state,
        )

        return {
            "registry_export": registry_export,
            "generation_evidence": generation_evidence,
            "facility_master": facility_master,
            "validated_input": json.dumps(validated_payload, ensure_ascii=False),
            "status": AgentStatus.SUCCESS.value,
        }
