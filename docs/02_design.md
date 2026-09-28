# Template Design Specification — ENE-C2-064

## Position in AgentCore Architecture

- **Agent Class**: `CertificateReconciliationGraph` (`src/graph/graph.py`, aliased `Graph`)
- **L1 Base**: AgentBaseGraph (L1 direct). Outer graph = `AgentBaseGraph`; `main` slot wraps an
  inner `BaseGraph` subgraph via `ReconcileGraphNode` (Cat 2 pattern).
- **Three-Layer Separation**:
  - State: flat TypedDict composition (`class State(AgentState)`, `src/schemas/state.py`) — no
    Pydantic/dataclass (msgpack incompatible)
  - Node: L1 inheritance (Template Method: `execute(self, state: dict) -> dict` override only)
  - Graph: composition (outer `register_nodes()` for 3-slot substitution; inner
    `CertificateReconciliationWorkflowGraph` for the 3-step domain workflow)

## Architecture Overview

### Node Configuration (outer backbone)

| Node | Responsibility | Input State | Output State | Inherits/Overrides |
|------|---------------|-------------|--------------|-------------------|
| initialize | schema_version, session_id, trust_level | — | — | InitializeNode (default) |
| pre_process (`InputValidateNode`) | S-1 trust gate (`VERIFIED_EXTERNAL`) + S-2 credential/path-traversal scan (reject) + non-regulated PII flag-and-redact on `facility_master` | `user_input` (JSON string) | `registry_export`, `generation_evidence`, `facility_master`, `validated_input` | `FunctionNode` |
| main (`ReconcileGraphNode`) | Dispatches into the inner reconciliation workflow (`EvidenceExtract` → `Reconcile` → `BriefRender`) | `validated_input` | `mismatches`, `exceptions`, `reconciled_records`, `brief` | `GraphNode` |
| post_process (`OutputValidateNode`) | S-3 citation-preservation gate: every `brief.mismatches`/`brief.exceptions` entry must carry `source_refs` already present in `state.mismatches`/`state.exceptions` | `brief`, `mismatches`, `exceptions` | `brief` (validated), `formatted_output` | `FunctionNode` |
| finalize | response_metadata, total_time_ms | — | — | FinalizeNode (default) |

### Inner workflow (`CertificateReconciliationWorkflowGraph`, `src/graph/domain_workflow_graph.py`)

| Node | Responsibility | Output |
|---|---|---|
| `evidence_extract` (`EvidenceExtractNode`) | LLM-normalizes certificate serial / facility ID / generation period / retirement status from registry export + generation evidence | `normalized_certificates`, `normalized_evidence`, `facility_master` |
| `reconcile` (`ReconcileNode`) | Calls the deterministic matcher (`src/services/service.py::reconcile_records` — pure function, no LLM) to exact-match `facility_id`+`period`+`certificate_serial` across sources; flags duplicate serials and mismatches | `mismatches`, `exceptions`, `reconciled_records` |
| `brief_render` (`BriefRenderNode`) | LLM assembles a structured, cited human-review brief; every claim references a `source_refs` produced by `reconcile` | `brief` |

### Data Flow

```
START → initialize → pre_process(InputValidate) → main(ReconcileGraphNode) → {route} → post_process(OutputValidate) → finalize → END
                                                          │ (inner: evidence_extract → reconcile → brief_render)
                                                        ↓ (retry, max 3)
                                                   pre_process
```

### State Definition (`src/schemas/state.py`)

| Field | Type | Purpose | Required |
|-------|------|---------|----------|
| `registry_export` | `NotRequired[list[dict]]` | Sanitized certificate registry export | No |
| `generation_evidence` | `NotRequired[list[dict]]` | Sanitized generation-evidence records | No |
| `facility_master` | `NotRequired[list[dict]]` | Sanitized (PII-redacted) facility master | No |
| `normalized_certificates` | `NotRequired[list[dict]]` | EvidenceExtract output (registry side) | No |
| `normalized_evidence` | `NotRequired[list[dict]]` | EvidenceExtract output (evidence side) | No |
| `mismatches` | `NotRequired[list[dict]]` | Reconcile output — cross-source mismatches | No |
| `exceptions` | `NotRequired[list[dict]]` | Reconcile output — duplicate/period exceptions | No |
| `reconciled_records` | `NotRequired[list[dict]]` | Reconcile output — matched records | No |
| `brief` | `NotRequired[dict]` | BriefRender/OutputValidate — cited human-review brief | No |
| `validated_input` | `NotRequired[str]` | JSON-serialized sanitized payload, passed to the inner subgraph via `GraphNode.extract_input()` | No |

**State Constraints (mandatory):**
- Flat TypedDict only (primitives + JSON-serializable types) — satisfied (all fields are `list[dict]`/`dict`)
- No JWT, API keys, credentials in State (checkpoint DB leakage)
- InvocationContext via `config["configurable"]` only (not in State)
- No Pydantic models, dataclass, arbitrary Python objects (msgpack incompatible)

## Framework Utilization

### Shared Components Used
- [x] InvocationContext (correlation_id, session_id, caller_trust_level)
- [ ] ConnectionPolicy (retry/timeout strategy) — default max_retry=3 sufficient, no custom policy
- [ ] SecurityViolationError — not raised by this template's node code (the framework reserves it for
      the S-1 trust-level authorization gate itself, `node_name/required/actual` signature); domain
      credential/path-traversal detection in `InputValidateNode` returns a fail-closed `ERROR` dict
      instead, consistent with the "no-raise, return ERROR" node contract
- [x] S-2: `_extra_security_gate_input()` — not overridden (default framework PII scan on
      `user_input`/`validated_input` is sufficient; domain-specific credential/path-traversal detection
      is business logic inside `InputValidateNode.execute()`, returning ERROR dicts, never raising)
- [x] S-3: `_extra_security_gate_output()` — implemented on `OutputValidateNode` (preservation-variant
      re-check: `formatted_output` must remain a dict; the citation-preservation filtering itself is
      business logic inside `execute()`, since raise-able
      validation belongs in `execute()`, not the hook)
- [x] S-4: `emit_trace_event()` — at least one domain-specific event inside every node's `execute()`
      (`input_validated`, `evidence_extracted`, `reconciliation_completed`, `brief_rendered`,
      `output_validated`; plus `reconciliation_dispatched`/`reconciliation_completed_outer` inside
      `ReconcileGraphNode.extract_input()`/`merge_output()`)

> **S-2/S-3 gate behaviour by node type (ADR-017):**
> - `FunctionNode` subclass → framework `@final` gate always runs automatically;
>   extend via `_extra_security_gate_input()` / `_extra_security_gate_output()` only
> - `GraphNode` (`ReconcileGraphNode`) → deliberate no-op passthrough (security gating is handled by
>   `InputValidateNode`/`OutputValidateNode` at the outer boundary; inner nodes run at `ANONYMOUS`
>   since trust is authenticated once at the outer backbone)
> - Custom `BaseNode` subclass → N/A (no custom `BaseNode` subclass in this template)

### Composition Pattern

- **Pattern**: GraphNode (subgraph) — Cat 2, outer `AgentBaseGraph` + `ReconcileGraphNode` wrapping
  inner `CertificateReconciliationWorkflowGraph` (`BaseGraph`)
- **Composition target**: `src/graph/domain_workflow_graph.py::CertificateReconciliationWorkflowGraph`
- **Error propagation strategy**: `propagate` (fail fast — inner errors surface as `SubgraphError`)

## Import Isolation Confirmation
- [x] Template does not import agenticstar-platform SDK (Level 0)
- [x] Import targets: framework/ and shared/ only (no agents/base/ required)

## Design Decision Record

| Decision | Option A | Option B | Chosen | Rationale |
|----------|----------|----------|--------|-----------|
| L1 base type | AgentBaseGraph | AutonomousBaseGraph | **AgentBaseGraph** | Fixed multi-step pipeline (extract → reconcile → cite-brief), not an autonomous reasoning loop — Cat 2, not Cat 3 |
| Composition pattern | Flat (Cat 1 style) | GraphNode + inner subgraph | **GraphNode + inner subgraph** | Cat 2 requires `main` slot wrapped by `GraphNode`; a flat MainNode chaining 3 business steps fails `gate-composition` |
| Deterministic matcher location | LLM-driven matching | Pure-function matcher in `src/services/` | **Pure-function matcher** | Exact/fuzzy `facility_id`+`period`+`certificate_serial` matching is deterministic — isolating it keeps `Reconcile` a thin, testable wrapper |
| S-3 gate design | Hook-only filtering | Business-logic check in `execute()` + preservation-variant hook | **Both** | Citation-preservation validation is raise-able/complex logic (belongs in `execute()`); the hook does a lightweight own-key consistency re-check |
