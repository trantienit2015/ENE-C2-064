"""AgentCore Platform v1.0"""

# ADR-005: State must be a flat TypedDict (see ADR-005 for the prohibited
# alternatives). LangGraph checkpoints use msgpack serialization, so only
# plain serializable fields are allowed. Do NOT add credentials or secrets.

from typing import NotRequired

from framework.schemas.agent_state import AgentState


# Type-check note: the wheel ships no py.typed, so mypy resolves AgentState to Any
# and reports every NotRequired below as valid-type. The fields are correct (the state
# contract requires NotRequired) -- the report is a packaging artifact, suppressed per field.
# Drop these ignores once the wheel ships py.typed.
class State(AgentState):
    """Agent state for the ENE-C2-064 certificate reconciliation pipeline."""

    # Raw caller inputs (sanitized copies produced by InputValidate)
    registry_export: NotRequired[list[dict]]  # type: ignore[valid-type]
    generation_evidence: NotRequired[list[dict]]  # type: ignore[valid-type]
    facility_master: NotRequired[list[dict]]  # type: ignore[valid-type]

    # Normalized records produced by EvidenceExtract (inner subgraph)
    normalized_certificates: NotRequired[list[dict]]  # type: ignore[valid-type]
    normalized_evidence: NotRequired[list[dict]]  # type: ignore[valid-type]

    # Reconciliation output produced by Reconcile (inner subgraph)
    mismatches: NotRequired[list[dict]]  # type: ignore[valid-type]
    exceptions: NotRequired[list[dict]]  # type: ignore[valid-type]
    reconciled_records: NotRequired[list[dict]]  # type: ignore[valid-type]

    # Rendered human-review brief produced by BriefRender (inner subgraph)
    brief: NotRequired[dict]  # type: ignore[valid-type]

    # Set by outer pre_process for the GraphNode -> inner subgraph handoff
    validated_input: NotRequired[str]  # type: ignore[valid-type]
