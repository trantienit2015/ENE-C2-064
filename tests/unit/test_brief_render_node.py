from framework.schemas.agent_status import AgentStatus

from src.nodes import brief_render_node
from src.nodes.brief_render_node import BriefRenderNode


class FakeLLM:
    def complete(self, prompt: str) -> str:
        return "summary text"


class CanonicalDictLLM:
    """Real BaseLLM.complete() returns a dict, not a bare string."""

    def complete(self, prompt: str) -> dict:
        return {"content": "canonical dict summary", "tool_calls": [], "model": "fake", "usage": {}}


class EmptyLLM:
    """LLM is configured but returns no usable content."""

    def complete(self, prompt: str) -> dict:
        return {"content": "", "tool_calls": [], "model": "fake", "usage": {}}


class TestBriefRenderNode:
    def test_success_renders_cited_brief(self):
        node = BriefRenderNode(llm=FakeLLM())
        state = {
            "mismatches": [
                {"facility_id": "F-9", "certificate_serial": "S-9", "issue_type": "id_mismatch", "source_refs": ["evidence:1"]}
            ],
            "exceptions": [
                {"type": "duplicate", "facility_id": "F-1", "details": "dup", "source_refs": ["registry-dup:F-1:2026-06:S-1"]}
            ],
        }
        out = node.execute(state)
        assert out["status"] == AgentStatus.SUCCESS
        brief = out["brief"]
        assert brief["mismatches"] == state["mismatches"]
        assert brief["exceptions"] == state["exceptions"]
        assert "evidence:1" in brief["brief"]["citations"]
        assert brief["brief"]["summary"] == "summary text"

    def test_missing_reconciliation_result_error(self):
        node = BriefRenderNode(llm=FakeLLM())
        out = node.execute({})
        assert out["status"] == AgentStatus.ERROR
        assert out["error_log"]

    def test_llm_none_falls_back_deterministic_no_crash(self):
        node = BriefRenderNode(llm=None)
        state = {
            "mismatches": [{"facility_id": "F-9", "source_refs": ["evidence:1"]}],
            "exceptions": [],
        }
        out = node.execute(state)
        assert out["status"] == AgentStatus.SUCCESS
        assert "1 mismatch" in out["brief"]["brief"]["summary"]
        assert "evidence:1" in out["brief"]["brief"]["citations"]

    def test_canonical_dict_llm_response_is_normalised(self):
        # Real BaseLLM.complete() returns {"content": str, ...}; must not crash
        # and must not leak the raw dict into the brief text field.
        node = BriefRenderNode(llm=CanonicalDictLLM())
        state = {
            "mismatches": [{"facility_id": "F-9", "source_refs": ["evidence:1"]}],
            "exceptions": [],
        }
        out = node.execute(state)
        assert out["status"] == AgentStatus.SUCCESS
        assert out["brief"]["brief"]["summary"] == "canonical dict summary"
        assert isinstance(out["brief"]["brief"]["summary"], str)

    def test_llm_empty_response_is_error_not_success(self):
        # LLM IS configured but returns nothing usable — a real LLM failure, must
        # not be swallowed into a fabricated deterministic SUCCESS.
        node = BriefRenderNode(llm=EmptyLLM())
        state = {
            "mismatches": [{"facility_id": "F-9", "source_refs": ["evidence:1"]}],
            "exceptions": [],
        }
        out = node.execute(state)
        assert out["status"] == AgentStatus.ERROR
        assert out["error_log"]


class TestBriefRenderNodeAuditEvents:
    def test_emits_on_reject_path(self, monkeypatch):
        events = []
        monkeypatch.setattr(brief_render_node, "emit_trace_event", lambda e, p, s: events.append(e))
        out = BriefRenderNode(llm=FakeLLM()).execute({})
        assert out["status"] == AgentStatus.ERROR
        assert "brief_render_received" in events

    def test_emits_deterministic_fallback_event_when_llm_none(self, monkeypatch):
        events = []
        monkeypatch.setattr(brief_render_node, "emit_trace_event", lambda e, p, s: events.append(e))
        out = BriefRenderNode(llm=None).execute({"mismatches": [], "exceptions": []})
        assert out["status"] == AgentStatus.SUCCESS
        assert "brief_render_deterministic_fallback" in events
