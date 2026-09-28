from framework.schemas.agent_status import AgentStatus

from src.nodes.output_validate_node import OutputValidateNode


class TestOutputValidateNode:
    def test_success_all_citations_valid(self):
        node = OutputValidateNode()
        state = {
            "mismatches": [{"facility_id": "F-9", "source_refs": ["evidence:1"]}],
            "exceptions": [],
            "brief": {
                "mismatches": [{"facility_id": "F-9", "source_refs": ["evidence:1"]}],
                "exceptions": [],
                "brief": {"summary": "ok", "citations": ["evidence:1"]},
            },
        }
        out = node.execute(state)
        assert out["status"] == AgentStatus.SUCCESS
        assert len(out["brief"]["mismatches"]) == 1

    def test_fabricated_claim_dropped_and_error(self):
        node = OutputValidateNode()
        state = {
            "mismatches": [{"facility_id": "F-9", "source_refs": ["evidence:1"]}],
            "exceptions": [],
            "brief": {
                # BriefRender (hypothetically compromised) introduces an extra
                # claim with a source_ref that Reconcile never produced.
                "mismatches": [
                    {"facility_id": "F-9", "source_refs": ["evidence:1"]},
                    {"facility_id": "F-FAKE", "source_refs": ["evidence:999-fabricated"]},
                ],
                "exceptions": [],
                "brief": {"summary": "ok", "citations": ["evidence:1"]},
            },
        }
        out = node.execute(state)
        assert out["status"] == AgentStatus.ERROR
        assert out["error_log"]
        assert len(out["brief"]["mismatches"]) == 1

    def test_extra_security_gate_output_hook_non_raising(self):
        node = OutputValidateNode()
        result = node._extra_security_gate_output({"formatted_output": {"mismatches": []}})
        assert isinstance(result, dict)

    def test_extra_security_gate_output_rejects_non_dict_output(self):
        node = OutputValidateNode()
        result = node._extra_security_gate_output({"formatted_output": "not-a-dict", "error_log": []})
        assert result["status"] == AgentStatus.ERROR
