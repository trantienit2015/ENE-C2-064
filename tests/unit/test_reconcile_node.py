from framework.schemas.agent_status import AgentStatus

from src.nodes import reconcile_node
from src.nodes.reconcile_node import ReconcileNode


class TestReconcileNode:
    def test_success_flags_mismatch(self):
        node = ReconcileNode()
        state = {
            "normalized_certificates": [{"facility_id": "F-1", "period": "2026-06", "certificate_serial": "S-1"}],
            "normalized_evidence": [
                {"facility_id": "F-1", "period": "2026-06", "certificate_serial": "S-1"},
                {"facility_id": "F-9", "period": "2026-06", "certificate_serial": "S-9"},
            ],
            "facility_master": [{"facility_id": "F-1"}],
        }
        out = node.execute(state)
        assert out["status"] == AgentStatus.SUCCESS
        assert len(out["mismatches"]) == 1
        assert out["mismatches"][0]["facility_id"] == "F-9"
        assert out["reconciled_records"]

    def test_duplicate_serial_flagged_as_exception(self):
        node = ReconcileNode()
        state = {
            "normalized_certificates": [
                {"facility_id": "F-1", "period": "2026-06", "certificate_serial": "S-1"},
                {"facility_id": "F-1", "period": "2026-06", "certificate_serial": "S-1"},
            ],
            "normalized_evidence": [{"facility_id": "F-1", "period": "2026-06", "certificate_serial": "S-1"}],
            "facility_master": [{"facility_id": "F-1"}],
        }
        out = node.execute(state)
        assert out["status"] == AgentStatus.SUCCESS
        assert len(out["exceptions"]) == 1
        assert out["exceptions"][0]["type"] == "duplicate"

    def test_empty_input_error(self):
        node = ReconcileNode()
        out = node.execute({"normalized_certificates": [], "normalized_evidence": [], "facility_master": []})
        assert out["status"] == AgentStatus.ERROR
        assert out["error_log"]


class TestReconcileNodeAuditEvents:
    def test_emits_on_reject_path(self, monkeypatch):
        events = []
        monkeypatch.setattr(reconcile_node, "emit_trace_event", lambda e, p, s: events.append(e))
        out = ReconcileNode().execute({"normalized_certificates": [], "normalized_evidence": [], "facility_master": []})
        assert out["status"] == AgentStatus.ERROR
        assert "reconcile_received" in events
