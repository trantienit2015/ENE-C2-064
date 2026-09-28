# ENE-C2-064 - Integration test: full graph compile + invoke (Cat 2 outer + inner).

import json

from framework.schemas.invocation_context import InvocationContext
from framework.schemas.trust_level import TrustLevel

from src.graph.graph import Graph


class FakeLLM:
    def complete(self, prompt: str) -> str:
        return "fake-summary: reconciliation reviewed"


VALID_PAYLOAD = json.dumps(
    {
        "registry_export": [
            {"facility_id": "F-001", "period": "2026-06", "certificate_serial": "CERT-1", "retirement_status": "active"},
            {"facility_id": "F-002", "period": "2026-06", "certificate_serial": "CERT-2", "retirement_status": "active"},
        ],
        "generation_evidence": [
            {"facility_id": "F-001", "period": "2026-06", "certificate_serial": "CERT-1"},
            {"facility_id": "F-003", "period": "2026-06", "certificate_serial": "CERT-9"},
        ],
        "facility_master": [
            {"facility_id": "F-001", "owner": "Jane Doe", "contact_email": "jane@example.com"},
            {"facility_id": "F-002"},
        ],
    }
)

EMPTY_PAYLOAD = ""


class TestAgentIntegration:
    def test_valid_payload_reaches_full_pipeline(self):
        agent = Graph(config={"max_retry": 1, "llm": FakeLLM()})
        agent.compile()
        ctx = InvocationContext(session_id="it-1", caller_trust_level=TrustLevel.VERIFIED_EXTERNAL, caller_id="reviewer-001")
        result = agent.invoke(VALID_PAYLOAD, ctx=ctx)

        assert len(result.get("node_history", [])) >= 4
        assert result["status"] in ("success", "error", "cancelled")

    def test_empty_payload_error(self):
        agent = Graph(config={"max_retry": 1, "llm": FakeLLM()})
        agent.compile()
        ctx = InvocationContext(session_id="it-2", caller_trust_level=TrustLevel.VERIFIED_EXTERNAL, caller_id="reviewer-001")
        result = agent.invoke(EMPTY_PAYLOAD, ctx=ctx)
        assert result["status"] in ("error", "cancelled")

    def test_insufficient_trust_denied(self):
        agent = Graph(config={"max_retry": 1, "llm": FakeLLM()})
        agent.compile()
        ctx = InvocationContext(session_id="it-3", caller_trust_level=TrustLevel.ANONYMOUS, caller_id="anon")
        result = agent.invoke(VALID_PAYLOAD, ctx=ctx)
        assert result["status"] in ("error", "cancelled")
