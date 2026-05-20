#!/usr/bin/env python3
"""Strict deterministic runtime evidence validator (non-blocking).

Inputs:
- docs/governance/runtime/latest_runtime_evidence.jsonl
- docs/governance/runtime_evidence_schema_v0.json

Outputs:
- docs/governance/reports/latest_runtime_evidence_validation.json
- docs/governance/reports/latest_runtime_evidence_validation.md
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from datetime import datetime
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


def validate(records: list[dict[str, Any]], schema: dict[str, Any], evidence_path: Path) -> dict[str, Any]:
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

        # hash chain consistency
        got_prev = rec.get("previous_record_hash")
        if idx == 1:
            if got_prev is not None:
                hash_chain_errors += 1
                rec_errors.append("genesis previous_record_hash must be null")
        else:
            if got_prev != prev_hash:
                hash_chain_errors += 1
                rec_errors.append("previous_record_hash chain mismatch")

        # self-attested explicit marker
        if not isinstance(rec.get("self_attested"), bool):
            rec_errors.append("self_attested must be boolean")
        elif rec.get("self_attested"):
            self_attested_count += 1

        ivr = rec.get("independent_verifier_ref")
        if ivr:
            independently_verified_count += 1

        est = rec.get("evidence_source_type")
        # independent claim consistency
        if est == "external_verifier" and not ivr:
            rec_errors.append("external_verifier evidence requires independent_verifier_ref")
        if ivr and rec.get("self_attested") is True:
            warnings.append(f"line {idx}: both independent_verifier_ref set and self_attested=true")

        # operational claims should include raw refs
        if t in {"deploy", "migrate", "rollback", "reconcile", "retry_reentry", "verifier_result", "invariant_result", "escalation_event", "break_glass_event"}:
            refs = rec.get("raw_log_refs")
            if not isinstance(refs, list) or len(refs) == 0:
                rec_errors.append("raw_log_refs required for operational claim")

        # unknown/null policy
        ad = rec.get("artifact_digest")
        ef = rec.get("env_fingerprint")
        if ad in UNKNOWN_POLICY_VALUES:
            unknown_policy_counts["artifact_digest"] += 1
            if not any(rc in {"artifact_digest_unknown_policy", "artifact_digest_unavailable"} for rc in (rec.get("reason_codes") or [])):
                rec_errors.append("artifact_digest unknown/null without explicit unknown policy reason code")
        if ef in UNKNOWN_POLICY_VALUES:
            unknown_policy_counts["env_fingerprint"] += 1
            if not any(rc in {"env_fingerprint_unknown_policy", "env_fingerprint_unavailable"} for rc in (rec.get("reason_codes") or [])):
                rec_errors.append("env_fingerprint unknown/null without explicit unknown policy reason code")

        if rec_errors:
            invalid_records += 1
            errors.extend([f"line {idx}: {e}" for e in rec_errors])
        else:
            valid_records += 1

        prev_hash = rec.get("record_hash") if isinstance(rec.get("record_hash"), str) else prev_hash

    hash_chain_valid = hash_chain_errors == 0 and record_hash_errors == 0

    trust_implications: list[str] = []
    if invalid_records > 0:
        trust_implications.append("Runtime evidence quality degraded: invalid records present.")
    if not hash_chain_valid:
        trust_implications.append("Hash-chain integrity degraded: tamper-evidence is unreliable.")
    if independently_verified_count == 0 and len(records) > 0:
        trust_implications.append("No independent verification references present; confidence must remain low.")
    if self_attested_count > independently_verified_count:
        trust_implications.append("Self-attested evidence dominates; anti-theater risk elevated.")

    status = "valid" if invalid_records == 0 and hash_chain_valid else "degraded"

    report = {
        "report_version": "v0-runtime-evidence-validation",
        "generated_at_utc": datetime.utcnow().isoformat() + "Z",
        "runtime_evidence_file": str(evidence_path.relative_to(ROOT)) if evidence_path.exists() else str(evidence_path),
        "schema_file": str(SCHEMA_PATH.relative_to(ROOT)),
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
        "trust_implications": trust_implications,
    }
    return report


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
    lines.append("## Missing Field Counts")
    lines.append(f"- {report['missing_field_counts']}")
    lines.append("")
    lines.append("## Unknown-Policy Usage Counts")
    lines.append(f"- {report['unknown_policy_usage_counts']}")
    lines.append("")
    lines.append("## Warnings")
    if report["warnings"]:
        for w in report["warnings"]:
            lines.append(f"- {w}")
    else:
        lines.append("- none")
    lines.append("")
    lines.append("## Errors")
    if report["errors"]:
        for e in report["errors"]:
            lines.append(f"- {e}")
    else:
        lines.append("- none")
    lines.append("")
    lines.append("## Trust Implications")
    if report["trust_implications"]:
        for t in report["trust_implications"]:
            lines.append(f"- {t}")
    else:
        lines.append("- none")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime-evidence", default=str(DEFAULT_JSONL))
    args = parser.parse_args()

    evidence_path = Path(args.runtime_evidence).resolve()
    REPORT_JSON.parent.mkdir(parents=True, exist_ok=True)

    schema = _load_schema()
    records = _read_jsonl(evidence_path)
    report = validate(records, schema, evidence_path)

    REPORT_JSON.write_text(json.dumps(report, indent=2) + "\n")
    REPORT_MD.write_text(render_md(report))

    print(str(REPORT_JSON.relative_to(ROOT)))
    print(str(REPORT_MD.relative_to(ROOT)))
    print(f"validation_status={report['validation_status']}")


if __name__ == "__main__":
    main()
