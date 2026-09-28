import json

from framework.schemas.agent_status import AgentStatus

from src.nodes import evidence_extract_node
from src.nodes.evidence_extract_node import EvidenceExtractNode


class FakeLLM:
    def __init__(self):
        self.calls = []

    def complete(self, prompt: str) -> str:
        self.calls.append(prompt)
        return "normalized"


class CanonicalDictLLM:
    """Real BaseLLM.complete() returns a dict, not a bare string."""

    def complete(self, prompt: str) -> dict:
        return {"content": "confirmed", "tool_calls": [], "model": "fake", "usage": {}}


class EmptyLLM:
    """LLM is configured but returns no usable content."""

    def complete(self, prompt: str) -> dict:
        return {"content": "", "tool_calls": [], "model": "fake", "usage": {}}


def _inner_input(**overrides):
    base = {
        "registry_export": [{"facility_id": " F-1 ", "period": "2026-06", "certificate_serial": "S-1"}],
        "generation_evidence": [{"facility_id": "F-1", "period": "2026-06", "certificate_serial": "S-1"}],
        "facility_master": [{"facility_id": "F-1"}],
    }
    base.update(overrides)
    return json.dumps(base)


class TestEvidenceExtractNode:
    def test_success_normalizes_records(self):
        llm = FakeLLM()
        node = EvidenceExtractNode(llm=llm)
        out = node.execute({"user_input": _inner_input()})
        assert out["status"] == AgentStatus.SUCCESS
        assert out["normalized_certificates"][0]["facility_id"] == "F-1"
        assert len(llm.calls) == 1

    def test_empty_registry_error(self):
        node = EvidenceExtractNode(llm=FakeLLM())
        out = node.execute({"user_input": json.dumps({"registry_export": [], "generation_evidence": [], "facility_master": []})})
        assert out["status"] == AgentStatus.ERROR
        assert out["error_log"]

    def test_invalid_json_error_no_llm_call(self):
        llm = FakeLLM()
        node = EvidenceExtractNode(llm=llm)
        out = node.execute({"user_input": "not json"})
        assert out["status"] == AgentStatus.ERROR
        assert llm.calls == []

    def test_llm_none_falls_back_deterministic_no_crash(self):
        node = EvidenceExtractNode(llm=None)
        out = node.execute({"user_input": _inner_input()})
        assert out["status"] == AgentStatus.SUCCESS
        assert out["normalized_certificates"][0]["facility_id"] == "F-1"

    def test_canonical_dict_llm_response_is_normalised(self):
        # Real BaseLLM.complete() returns {"content": str, ...}; must not crash.
        node = EvidenceExtractNode(llm=CanonicalDictLLM())
        out = node.execute({"user_input": _inner_input()})
        assert out["status"] == AgentStatus.SUCCESS
        assert out["normalized_certificates"][0]["facility_id"] == "F-1"

    def test_llm_empty_response_is_error_not_success(self):
        # LLM IS configured but returns nothing usable — a real LLM failure, must
        # not be swallowed into a fabricated SUCCESS.
        node = EvidenceExtractNode(llm=EmptyLLM())
        out = node.execute({"user_input": _inner_input()})
        assert out["status"] == AgentStatus.ERROR
        assert out["error_log"]


class TestEvidenceExtractNodeAuditEvents:
    def test_emits_on_reject_path(self, monkeypatch):
        events = []
        monkeypatch.setattr(evidence_extract_node, "emit_trace_event", lambda e, p, s: events.append(e))
        out = EvidenceExtractNode(llm=FakeLLM()).execute({"user_input": "not json"})
        assert out["status"] == AgentStatus.ERROR
        assert "evidence_extract_received" in events

    def test_emits_deterministic_fallback_event_when_llm_none(self, monkeypatch):
        events = []
        monkeypatch.setattr(evidence_extract_node, "emit_trace_event", lambda e, p, s: events.append(e))
        out = EvidenceExtractNode(llm=None).execute({"user_input": _inner_input()})
        assert out["status"] == AgentStatus.SUCCESS
        assert "evidence_extract_deterministic_fallback" in events
