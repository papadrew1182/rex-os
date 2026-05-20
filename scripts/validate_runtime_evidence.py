#!/usr/bin/env python3
"""Strict deterministic runtime evidence validator (non-blocking).

Flow:
1) Validate operational records currently present in runtime JSONL.
2) Append hash-chained validation summary record into the same JSONL ledger.
3) Re-validate final file including summary record.
4) Emit sidecar validation reports with explicit caveat about validator self-attestation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "docs" / "governance" / "runtime_evidence_schema_v0.json"
DEFAULT_JSONL = ROOT / "docs" / "governance" / "runtime" / "latest_runtime_evidence.jsonl"
REPORT_JSON = ROOT / "docs" / "governance" / "reports" / "latest_runtime_evidence_validation.json"
REPORT_MD = ROOT / "docs" / "governance" / "reports" / "latest_runtime_evidence_validation.md"

UNKNOWN_POLICY_VALUES = {None, "unknown"}


def _sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _normalize_for_hash(rec: dict[str, Any]) -> str:
    x = dict(rec)
    x.pop("record_hash", None)
    return json.dumps(x, sort_keys=True, separators=(",", ":"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if not path.exists():
        return out
    for i, line in enumerate(path.read_text().splitlines(), start=1):
        s = line.strip()
        if not s:
            continue
        obj = json.loads(s)
        if not isinstance(obj, dict):
            raise ValueError(f"line {i}: expected object")
        out.append(obj)
    return out


def _write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, separators=(",", ":")) + "\n")


def _parse_ts(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
        return True
    except Exception:
        return False


def _load_schema() -> dict[str, Any]:
    return json.loads(SCHEMA_PATH.read_text())


def _metrics_from_records(records: list[dict[str, Any]], schema: dict[str, Any]) -> dict[str, Any]:
    required = set(schema.get("required", []))
    props = schema.get("properties", {})
    valid_transition = set(props.get("transition_type", {}).get("enum", []))
    valid_actor = set(props.get("actor_type", {}).get("enum", []))
    valid_decision = set(props.get("decision", {}).get("enum", []))

    errors: list[str] = []
    warnings: list[str] = []
    missing_field_counts: Counter[str] = Counter()
    unknown_policy_counts: Counter[str] = Counter()

    valid_records = 0
    invalid_records = 0
    self_attested_count = 0
    independently_verified_count = 0

    prev_hash: str | None = None
    hash_chain_errors = 0
    record_hash_errors = 0

    for idx, rec in enumerate(records, start=1):
        rec_errors: list[str] = []
        missing = sorted(list(required - set(rec.keys())))
        for m in missing:
            missing_field_counts[m] += 1
            rec_errors.append(f"missing required field: {m}")

        t = rec.get("transition_type")
        if t not in valid_transition:
            rec_errors.append(f"invalid transition_type: {t}")
        a = rec.get("actor_type")
        if a not in valid_actor:
            rec_errors.append(f"invalid actor_type: {a}")
        d = rec.get("decision")
        if d not in valid_decision:
            rec_errors.append(f"invalid decision: {d}")
        if not _parse_ts(rec.get("timestamp_utc")):
            rec_errors.append("timestamp_utc not parseable")

        if not rec.get("record_hash"):
            rec_errors.append("record_hash missing")
        else:
            expected = _sha256_hex(_normalize_for_hash(rec))
            if rec.get("record_hash") != expected:
                record_hash_errors += 1
                rec_errors.append("record_hash mismatch")

        got_prev = rec.get("previous_record_hash")
        if idx == 1:
            if got_prev is not None:
                hash_chain_errors += 1
                rec_errors.append("genesis previous_record_hash must be null")
        else:
            if got_prev != prev_hash:
                hash_chain_errors += 1
                rec_errors.append("previous_record_hash chain mismatch")

        if not isinstance(rec.get("self_attested"), bool):
            rec_errors.append("self_attested must be boolean")
        elif rec.get("self_attested"):
            self_attested_count += 1

        ivr = rec.get("independent_verifier_ref")
        if ivr:
            independently_verified_count += 1

        est = rec.get("evidence_source_type")
        if est == "external_verifier" and not ivr:
            rec_errors.append("external_verifier evidence requires independent_verifier_ref")
        if ivr and rec.get("self_attested") is True:
            warnings.append(f"line {idx}: both independent_verifier_ref set and self_attested=true")

        refs = rec.get("raw_log_refs")
        if t in {"deploy", "migrate", "rollback", "reconcile", "retry_reentry", "verifier_result", "invariant_result", "escalation_event", "break_glass_event"}:
            if not isinstance(refs, list) or len(refs) == 0:
                rec_errors.append("raw_log_refs required for operational claim")

        ad = rec.get("artifact_digest")
        ef = rec.get("env_fingerprint")
        rcodes = rec.get("reason_codes") or []
        if ad in UNKNOWN_POLICY_VALUES:
            unknown_policy_counts["artifact_digest"] += 1
            if not any(rc in {"artifact_digest_unknown_policy", "artifact_digest_unavailable"} for rc in rcodes):
                rec_errors.append("artifact_digest unknown/null without explicit unknown policy reason code")
        if ef in UNKNOWN_POLICY_VALUES:
            unknown_policy_counts["env_fingerprint"] += 1
            if not any(rc in {"env_fingerprint_unknown_policy", "env_fingerprint_unavailable"} for rc in rcodes):
                rec_errors.append("env_fingerprint unknown/null without explicit unknown policy reason code")

        if rec_errors:
            invalid_records += 1
            errors.extend([f"line {idx}: {e}" for e in rec_errors])
        else:
            valid_records += 1

        prev_hash = rec.get("record_hash") if isinstance(rec.get("record_hash"), str) else prev_hash

    hash_chain_valid = hash_chain_errors == 0 and record_hash_errors == 0
    status = "valid" if invalid_records == 0 and hash_chain_valid else "degraded"
    return {
        "validation_status": status,
        "summary": {
            "total_records": len(records),
            "valid_records": valid_records,
            "invalid_records": invalid_records,
            "hash_chain_valid": hash_chain_valid,
            "hash_chain_invalid": not hash_chain_valid,
            "self_attested_count": self_attested_count,
            "independently_verified_count": independently_verified_count,
        },
        "missing_field_counts": dict(missing_field_counts),
        "unknown_policy_usage_counts": dict(unknown_policy_counts),
        "warnings": warnings,
        "errors": errors,
    }


def _extract_correlation_id(records: list[dict[str, Any]]) -> str:
    if records:
        cid = records[-1].get("correlation_id")
        if isinstance(cid, str) and cid:
            return cid
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    return f"rex-reconcile-{now.replace(':', '').replace('-', '')}"


def _append_validation_summary_record(records: list[dict[str, Any]], pre_metrics: dict[str, Any]) -> dict[str, Any]:
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    corr = _extract_correlation_id(records)
    prev_hash = records[-1]["record_hash"] if records else None
    s = pre_metrics["summary"]
    status = pre_metrics["validation_status"]
    warnings_count = len(pre_metrics["warnings"])
    errors_count = len(pre_metrics["errors"])
    decision = "allow" if status == "valid" else "escalate"
    reason_codes = [
        "validator_summary_record",
        f"validation_status_{status}",
        "non_enforcing",
    ]
    if status != "valid":
        reason_codes.append("validation_degraded")

    rec: dict[str, Any] = {
        "event_id": f"evt-{_sha256_hex(corr + '-validation-summary')[:16]}",
        "timestamp_utc": now,
        "transition_type": "verifier_result",
        "actor_type": "policy_engine",
        "actor_id": "runtime_evidence_validator",
        "target_service": "rex-governance",
        "target_env": "audit",
        "source_commit_sha": records[-1].get("source_commit_sha") if records else "0000000",
        "artifact_digest": "sha256:" + _sha256_hex(json.dumps(pre_metrics, sort_keys=True)),
        "env_fingerprint": "validator:v0",
        "correlation_id": corr,
        "evidence_strength": "strong" if status == "valid" else "medium",
        "evidence_source_type": "external_verifier",
        "self_attested": False,
        "independent_verifier_ref": "docs/governance/reports/latest_runtime_evidence_validation.json",
        "raw_log_refs": [
            "docs/governance/reports/latest_runtime_evidence_validation.json",
            "docs/governance/reports/latest_runtime_evidence_validation.md",
        ],
        "invariant_results": [
            {"invariant_id": "INV-EVIDENCE-VALIDATION-STATUS", "status": "pass" if status == "valid" else "warn", "verifier_ref": "runtime_evidence_validator"},
            {"invariant_id": "INV-EVIDENCE-TOTAL-RECORDS", "status": "pass", "verifier_ref": str(s["total_records"])},
            {"invariant_id": "INV-EVIDENCE-VALID-RECORDS", "status": "pass" if s["invalid_records"] == 0 else "warn", "verifier_ref": str(s["valid_records"])},
            {"invariant_id": "INV-EVIDENCE-INVALID-RECORDS", "status": "pass" if s["invalid_records"] == 0 else "warn", "verifier_ref": str(s["invalid_records"])},
            {"invariant_id": "INV-EVIDENCE-HASH-CHAIN", "status": "pass" if s["hash_chain_valid"] else "fail", "verifier_ref": str(s["hash_chain_valid"])},
            {"invariant_id": "INV-EVIDENCE-WARNING-COUNT", "status": "warn" if warnings_count > 0 else "pass", "verifier_ref": str(warnings_count)},
            {"invariant_id": "INV-EVIDENCE-ERROR-COUNT", "status": "warn" if errors_count > 0 else "pass", "verifier_ref": str(errors_count)},
            {"invariant_id": "INV-EVIDENCE-SELF-ATTESTED-COUNT", "status": "pass", "verifier_ref": str(s["self_attested_count"])},
            {"invariant_id": "INV-EVIDENCE-INDEPENDENT-COUNT", "status": "pass", "verifier_ref": str(s["independently_verified_count"])},
        ],
        "decision": decision,
        "reason_codes": reason_codes,
        "previous_record_hash": prev_hash,
    }
    rec["record_hash"] = _sha256_hex(_normalize_for_hash(rec))
    records.append(rec)
    return rec


def _trust_implications(pre: dict[str, Any], final: dict[str, Any]) -> list[str]:
    out: list[str] = []
    if pre["summary"]["invalid_records"] > 0:
        out.append("Operational records include invalid entries before summary append.")
    if not pre["summary"]["hash_chain_valid"]:
        out.append("Operational hash chain invalid before summary append.")
    if final["summary"]["invalid_records"] > 0:
        out.append("Final ledger (including summary) contains invalid entries.")
    if not final["summary"]["hash_chain_valid"]:
        out.append("Final ledger hash chain invalid after summary append.")
    if final["summary"]["independently_verified_count"] == 0 and final["summary"]["total_records"] > 0:
        out.append("No independent verifier refs present in ledger.")
    if final["summary"]["self_attested_count"] > final["summary"]["independently_verified_count"]:
        out.append("Self-attested evidence dominates ledger.")
    out.append("Caveat: validator summary record is generated by the same deterministic validator process; it attests pre-append validation and then final-file consistency, but is not an external third-party attestation.")
    return out


def render_md(report: dict[str, Any]) -> str:
    s = report["summary"]
    lines = ["# Runtime Evidence Validation", ""]
    lines.append(f"- Generated UTC: `{report['generated_at_utc']}`")
    lines.append(f"- Validation status: `{report['validation_status']}`")
    lines.append(f"- Runtime evidence file: `{report['runtime_evidence_file']}`")
    lines.append("")
    lines.append("## Summary")
    lines.append(f"- total_records: {s['total_records']}")
    lines.append(f"- valid_records: {s['valid_records']}")
    lines.append(f"- invalid_records: {s['invalid_records']}")
    lines.append(f"- hash_chain_valid: {s['hash_chain_valid']}")
    lines.append(f"- hash_chain_invalid: {s['hash_chain_invalid']}")
    lines.append(f"- self_attested_count: {s['self_attested_count']}")
    lines.append(f"- independently_verified_count: {s['independently_verified_count']}")
    lines.append("")
    lines.append("## Validation Record")
    lines.append(f"- transition_type: {report['validation_summary_record']['transition_type']}")
    lines.append(f"- actor_type: {report['validation_summary_record']['actor_type']}")
    lines.append(f"- actor_id: {report['validation_summary_record']['actor_id']}")
    lines.append(f"- decision: {report['validation_summary_record']['decision']}")
    lines.append("")
    lines.append("## Missing Field Counts")
    lines.append(f"- {report['missing_field_counts']}")
    lines.append("")
    lines.append("## Unknown-Policy Usage Counts")
    lines.append(f"- {report['unknown_policy_usage_counts']}")
    lines.append("")
    lines.append("## Warnings")
    for w in report["warnings"] or ["none"]:
        lines.append(f"- {w}")
    lines.append("")
    lines.append("## Errors")
    for e in report["errors"] or ["none"]:
        lines.append(f"- {e}")
    lines.append("")
    lines.append("## Trust Implications")
    for t in report["trust_implications"]:
        lines.append(f"- {t}")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime-evidence", default=str(DEFAULT_JSONL))
    args = parser.parse_args()

    evidence_path = Path(args.runtime_evidence).resolve()
    REPORT_JSON.parent.mkdir(parents=True, exist_ok=True)

    schema = _load_schema()
    records = _read_jsonl(evidence_path)

    # Drop prior validation summary record if present to avoid accumulation loops.
    records = [r for r in records if not (r.get("actor_id") == "runtime_evidence_validator" and r.get("transition_type") in {"verifier_result", "invariant_result"})]

    pre = _metrics_from_records(records, schema)
    summary_record = _append_validation_summary_record(records, pre)
    _write_jsonl(evidence_path, records)

    final = _metrics_from_records(records, schema)
    report = {
        "report_version": "v0-runtime-evidence-validation",
        "generated_at_utc": datetime.utcnow().isoformat() + "Z",
        "runtime_evidence_file": str(evidence_path.relative_to(ROOT)) if evidence_path.exists() else str(evidence_path),
        "schema_file": str(SCHEMA_PATH.relative_to(ROOT)),
        "validation_status": final["validation_status"],
        "summary": final["summary"],
        "missing_field_counts": final["missing_field_counts"],
        "unknown_policy_usage_counts": final["unknown_policy_usage_counts"],
        "warnings": final["warnings"],
        "errors": final["errors"],
        "trust_implications": _trust_implications(pre, final),
        "validation_process": {
            "pre_append_validation_status": pre["validation_status"],
            "post_append_validation_status": final["validation_status"],
            "self_attestation_caveat": "summary record is emitted by validator itself; deterministic but not third-party attestation",
        },
        "validation_summary_record": {
            "event_id": summary_record["event_id"],
            "transition_type": summary_record["transition_type"],
            "actor_type": summary_record["actor_type"],
            "actor_id": summary_record["actor_id"],
            "correlation_id": summary_record["correlation_id"],
            "decision": summary_record["decision"],
            "previous_record_hash": summary_record["previous_record_hash"],
            "record_hash": summary_record["record_hash"],
            "reason_codes": summary_record["reason_codes"],
        },
    }

    REPORT_JSON.write_text(json.dumps(report, indent=2) + "\n")
    REPORT_MD.write_text(render_md(report))

    print(str(REPORT_JSON.relative_to(ROOT)))
    print(str(REPORT_MD.relative_to(ROOT)))
    print(f"validation_status={report['validation_status']}")


if __name__ == "__main__":
    main()
