import json

from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel

from src.nodes import input_validate_node
from src.nodes.input_validate_node import InputValidateNode


def _payload(**overrides):
    base = {
        "registry_export": [{"facility_id": "F-1", "period": "2026-06", "certificate_serial": "S-1"}],
        "generation_evidence": [{"facility_id": "F-1", "period": "2026-06", "certificate_serial": "S-1"}],
        "facility_master": [{"facility_id": "F-1", "owner": "Jane Doe", "contact_email": "jane@example.com"}],
    }
    base.update(overrides)
    return json.dumps(base)


class TestInputValidateNode:
    def test_success_sanitizes_and_redacts_pii(self):
        node = InputValidateNode()
        out = node.execute({"user_input": _payload()})
        assert out["status"] == AgentStatus.SUCCESS
        assert out["facility_master"][0]["owner"] == "***REDACTED***"
        assert out["facility_master"][0]["contact_email"] == "***REDACTED***"
        assert json.loads(out["validated_input"])["registry_export"]

    def test_empty_input_error(self):
        node = InputValidateNode()
        out = node.execute({"user_input": ""})
        assert out["status"] == AgentStatus.ERROR
        assert out["error_log"]

    def test_invalid_json_error(self):
        node = InputValidateNode()
        out = node.execute({"user_input": "not json"})
        assert out["status"] == AgentStatus.ERROR
        assert out["error_log"]

    def test_credential_pattern_rejected_no_raise(self):
        node = InputValidateNode()
        out = node.execute({"user_input": "Bearer abcdefghij1234567890"})
        assert out["status"] == AgentStatus.ERROR
        assert out["error_log"]

    def test_trust_gate_denies_anonymous(self):
        node = InputValidateNode()
        out = node({"caller_trust_level": TrustLevel.ANONYMOUS.value, "user_input": _payload()})
        assert str(out["status"]).lower().endswith("error")
        assert any("S-1 trust gate denied" in e for e in out.get("error_log", []))

    def test_trust_gate_allows_verified_external(self):
        node = InputValidateNode()
        out = node({"caller_trust_level": TrustLevel.VERIFIED_EXTERNAL.value, "user_input": _payload()})
        assert out["status"] == AgentStatus.SUCCESS.value


class TestInputValidateNodeAuditEvents:
    def test_emits_on_reject_path(self, monkeypatch):
        events = []
        monkeypatch.setattr(input_validate_node, "emit_trace_event", lambda e, p, s: events.append(e))
        out = InputValidateNode().execute({"user_input": ""})
        assert out["status"] == AgentStatus.ERROR
        assert "input_validate_received" in events

    def test_emits_on_success_path(self, monkeypatch):
        events = []
        monkeypatch.setattr(input_validate_node, "emit_trace_event", lambda e, p, s: events.append(e))
        out = InputValidateNode().execute({"user_input": _payload()})
        assert out["status"] == AgentStatus.SUCCESS
        assert {"input_validate_received", "input_validated"}.issubset(set(events))
        for name in events:
            assert not (isinstance(name, str) and name in {"node_start", "node_complete", "node_error"})
