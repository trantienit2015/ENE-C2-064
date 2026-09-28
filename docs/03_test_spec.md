# Test Specification — ENE-C2-064

## Test Strategy
- Coverage target: every node ≥1 unit success + ≥1 error/edge path; full graph ≥1 integration compile+invoke
- Test types: Unit (`tests/unit/`), Integration (`tests/integration/`), Proof-of-Boundary (`tests/proof_of_boundary/`)

## Framework Compliance Tests (Mandatory)

| TC-ID | Test | Expected Result | Result |
|-------|------|----------------|--------|
| TC-01 | State contract: flat TypedDict | Type check pass, no Pydantic/dataclass | PASS |
| TC-02 | SecurityViolationError fires on invalid input | Error raised (credential/path-traversal pattern in `InputValidateNode`) | PASS |
| TC-03 | No JWT/Credential in State | CI `gate-credential-scan`: 0 violations | PASS |
| TC-04 | InvocationContext via configurable only | Direct access raises error; never stored in State post-invoke | PASS |
| TC-05 | S-4: no duplicate lifecycle events in `execute()` | `node_start`/`node_complete`/`node_error` absent from `execute()` body | PASS |
| TC-06 | S-2: `_security_gate_input()` not overridden (`FunctionNode` subclass) | `TypeError` raised at class definition if overridden | PASS |
| TC-07 | S-3: `_security_gate_output()` not overridden (`FunctionNode` subclass) | `TypeError` raised at class definition if overridden | PASS |
| TC-08 | `required_trust_level` enforced | Insufficient trust (`ANONYMOUS`) on `InputValidateNode` → refused | PASS |
| TC-09 | S-2: `_extra_security_gate_input()` | Default framework PII scan sufficient; domain credential/path-traversal check done as business logic in `InputValidateNode.execute()` (raises `SecurityViolationError`) | PASS |
| TC-10 | S-3: `_extra_security_gate_output()` non-trivial | `OutputValidateNode._extra_security_gate_output()` re-checks `formatted_output` is a dict (preservation-variant own-key check) | PASS |
| TC-11 | S-4: at least one domain `emit_trace_event()` inside each `execute()` | `input_validated`, `evidence_extracted`, `reconciliation_completed`, `brief_rendered`, `output_validated` — one per node | PASS |

## Proof-of-Boundary Tests (Mandatory)

| PB-ID | Boundary | Test | Expected Result | Result |
|-------|----------|------|----------------|--------|
| PB-1 | BaseNode → EventEmitter | `emit_trace_event()` fires on every invocation path | No silent failures | PASS |
| PB-2 | State serialization | Post-invoke State is primitives/list/dict only | No Pydantic/dataclass | PASS |
| PB-3 | Level 2 → External service | N/A — no external service call in this template (deterministic in-process matcher; LLM client injected via constructor) | N/A |
| PB-4 | Import isolation | No Level 0 imports | AST scan: 0 violations | PASS |
| PB-5 | Checkpoint safety | No JWT/Pydantic in checkpoint | Inspection pass | PASS |
| PB-6 | Invoke execution order | `__call__()`: S-1 → S-4 `node_start` → S-2 → `execute()` → S-3 → S-4 `node_complete`, for every `FunctionNode` under `src/nodes/` (`ReconcileGraphNode` excluded — `GraphNode` delegates gating to inner subgraph) | Order verified | PASS |
| PB-7 | HITL interrupt propagation *(conditional)* | `hitl.enabled` is not set in `config/agent.yaml` for this template | Auto-waived — non-HITL | Auto-waived |

> **Pre-review gate checklist:** PB-1 through PB-6 are mandatory. PB-7 auto-waived (non-HITL template).

## Business Logic Tests

| TC-ID | Test | Input | Expected Result | Result |
|-------|------|-------|----------------|--------|
| BL-01 | Exact-match reconciliation (no mismatch) | registry + evidence share identical `facility_id`+`period`+`certificate_serial` | `mismatches == []`, `reconciled_records` has 1 entry | PASS |
| BL-02 | Cross-source mismatch flagged with citation | evidence references a `facility_id`/`certificate_serial` combination absent from the registry export | `mismatches` has 1 entry with `issue_type` and `source_refs` | PASS |
| BL-03 | Duplicate certificate serial in registry flagged as exception | two registry records share the same `facility_id`+`period`+`certificate_serial` | `exceptions` has 1 entry, `type == "duplicate"` | PASS |
| BL-04 | S-3 citation-preservation gate drops fabricated claims | `OutputValidateNode` fed a brief containing a claim whose `source_refs` was never produced by `Reconcile` | fabricated entry dropped, `status == ERROR`, `error_log` records the drop | PASS |
| BL-05 | Non-regulated PII redaction in `facility_master` | `owner`/`contact_email` fields present in facility master | Redacted to `***REDACTED***` in `InputValidateNode` output (not rejected — flag-and-redact, per §4 row 1) | PASS |

## Test Execution Summary
- Execution date: 2026-07-18
- Total tests: unit (7 files) + integration (1 file, 3 cases) + proof_of_boundary (4 files)
- Pass: run locally via `pytest tests/ -v` before push (CI wheel is gate of record)
- Coverage: every node has ≥1 success + ≥1 error/edge unit test; full graph has ≥1 integration compile+invoke
