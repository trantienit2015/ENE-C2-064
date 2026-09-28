from src.services.service import reconcile_records


class TestReconcileRecords:
    def test_exact_match_no_mismatch(self):
        registry = [{"facility_id": "F-1", "period": "2026-06", "certificate_serial": "S-1"}]
        evidence = [{"facility_id": "F-1", "period": "2026-06", "certificate_serial": "S-1"}]
        result = reconcile_records(registry, evidence, [{"facility_id": "F-1"}])
        assert result["mismatches"] == []
        assert result["exceptions"] == []
        assert len(result["reconciled_records"]) == 1

    def test_unknown_facility_flags_id_mismatch(self):
        registry = [{"facility_id": "F-1", "period": "2026-06", "certificate_serial": "S-1"}]
        evidence = [{"facility_id": "F-9", "period": "2026-06", "certificate_serial": "S-9"}]
        result = reconcile_records(registry, evidence, [{"facility_id": "F-1"}])
        assert len(result["mismatches"]) == 1
        assert result["mismatches"][0]["issue_type"] == "id_mismatch"
        assert result["mismatches"][0]["source_refs"] == ["evidence:0"]

    def test_known_facility_wrong_period_flags_period_mismatch(self):
        registry = [{"facility_id": "F-1", "period": "2026-06", "certificate_serial": "S-1"}]
        evidence = [{"facility_id": "F-1", "period": "2026-07", "certificate_serial": "S-1"}]
        result = reconcile_records(registry, evidence, [{"facility_id": "F-1"}])
        assert len(result["mismatches"]) == 1
        assert result["mismatches"][0]["issue_type"] == "period_mismatch"

    def test_duplicate_registry_serial_flagged(self):
        registry = [
            {"facility_id": "F-1", "period": "2026-06", "certificate_serial": "S-1"},
            {"facility_id": "F-1", "period": "2026-06", "certificate_serial": "S-1"},
        ]
        evidence = [{"facility_id": "F-1", "period": "2026-06", "certificate_serial": "S-1"}]
        result = reconcile_records(registry, evidence, [{"facility_id": "F-1"}])
        assert len(result["exceptions"]) == 1
        assert result["exceptions"][0]["type"] == "duplicate"
