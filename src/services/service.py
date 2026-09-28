"""AgentCore Platform v1.0"""

# Service layer: deterministic domain logic. Must NOT contain LLM calls,
# routing, or credentials. Pure functions only — no side effects, no State,
# no InvocationContext. This is a "shared/tools/" style matcher: it is intentionally
# isolated here so the Reconcile node stays a thin FunctionNode wrapper.

from __future__ import annotations

from typing import Any


def _record_key(record: dict[str, Any]) -> tuple[Any, Any, Any]:
    return (
        record.get("facility_id"),
        record.get("period"),
        record.get("certificate_serial"),
    )


def reconcile_records(
    registry_export: list[dict[str, Any]],
    generation_evidence: list[dict[str, Any]],
    facility_master: list[dict[str, Any]],
) -> dict[str, Any]:
    """Deterministic exact-match reconciliation across three sources.

    Flags:
      - mismatches: an evidence record whose facility_id/period/certificate_serial
        combination is not found (exactly) in the registry export.
      - exceptions: duplicate certificate_serial within the registry export, or
        overlapping periods for the same facility_id + certificate_serial.
    """
    registry_by_key: dict[tuple[Any, Any, Any], dict[str, Any]] = {}
    duplicate_keys: set[tuple[Any, Any, Any]] = set()
    for idx, rec in enumerate(registry_export):
        key = _record_key(rec)
        if key in registry_by_key:
            duplicate_keys.add(key)
        else:
            registry_by_key[key] = {**rec, "_source_ref": f"registry:{idx}"}

    facility_ids = {rec.get("facility_id") for rec in facility_master}

    mismatches: list[dict[str, Any]] = []
    reconciled: list[dict[str, Any]] = []
    for idx, ev in enumerate(generation_evidence):
        key = _record_key(ev)
        source_ref = f"evidence:{idx}"
        registry_rec = registry_by_key.get(key)
        if registry_rec is None:
            issue_type = "id_mismatch" if ev.get("facility_id") not in facility_ids else "period_mismatch"
            mismatches.append(
                {
                    "facility_id": ev.get("facility_id"),
                    "certificate_serial": ev.get("certificate_serial"),
                    "issue_type": issue_type,
                    "registry_value": None,
                    "evidence_value": ev,
                    "source_refs": [source_ref],
                }
            )
            continue
        reconciled.append({**ev, "_source_refs": [source_ref, registry_rec["_source_ref"]]})

    exceptions: list[dict[str, Any]] = []
    for key in duplicate_keys:
        exceptions.append(
            {
                "type": "duplicate",
                "facility_id": key[0],
                "details": f"duplicate certificate_serial {key[2]!r} for facility {key[0]!r} in registry export",
                "source_refs": [f"registry-dup:{key[0]}:{key[1]}:{key[2]}"],
            }
        )

    return {
        "mismatches": mismatches,
        "exceptions": exceptions,
        "reconciled_records": reconciled,
    }
