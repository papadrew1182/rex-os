#!/usr/bin/env python3
"""Minimal deterministic governance scorer stub (non-enforcing).

Reads governance artifacts and optional runtime evidence JSONL and emits:
- docs/governance/reports/latest_governance_score.json
- docs/governance/reports/latest_governance_score.md
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs" / "governance"
REPORTS = DOCS / "reports"

INPUTS = {
    "invariants": DOCS / "invariants_v0.yaml",
    "evidence_schema": DOCS / "evidence_ledger_v0_schema.json",
    "policy": DOCS / "policy_engine_v0.md",
    "trust": DOCS / "trust_boundaries_v0.md",
    "anti_theater": DOCS / "anti_theater_rules_v0.md",
    "runtime_schema": DOCS / "runtime_evidence_schema_v0.json",
}

DEFAULT_RUNTIME_EVIDENCE = DOCS / "examples" / "runtime_evidence_sample.jsonl"

DEBT_CATEGORIES = [
    "ungated_transitions",
    "unverifiable_claims",
    "missing_provenance",
    "missing_rollback_proof",
    "detector_blind_spots",
    "heuristic_when_deterministic_possible",
    "unsafe_autonomous_execution_surfaces",
]


def _pct(num: int, den: int) -> float:
    return 0.0 if den <= 0 else round((num / den) * 100.0, 2)


def _read_inputs() -> dict[str, Any]:
    missing = [k for k, p in INPUTS.items() if not p.exists()]
    if missing:
        raise FileNotFoundError(f"Missing required governance artifacts: {missing}")

    return {
        "invariants": yaml.safe_load(INPUTS["invariants"].read_text()),
        "evidence_schema": json.loads(INPUTS["evidence_schema"].read_text()),
        "policy_md": INPUTS["policy"].read_text(),
        "trust_md": INPUTS["trust"].read_text(),
        "anti_md": INPUTS["anti_theater"].read_text(),
        "runtime_schema": json.loads(INPUTS["runtime_schema"].read_text()),
    }


def _parse_runtime_jsonl(path: Path | None) -> list[dict[str, Any]]:
    if path is None or not path.exists():
        return []
    records: list[dict[str, Any]] = []
    for idx, line in enumerate(path.read_text().splitlines(), start=1):
        raw = line.strip()
        if not raw:
            continue
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSONL line {idx} in {path}: {e}") from e
        if not isinstance(obj, dict):
            raise ValueError(f"Invalid JSONL line {idx} in {path}: expected object")
        records.append(obj)
    return records


def _confidence(missing_inputs: list[str], independent_ratio: float, self_ratio: float) -> str:
    if missing_inputs:
        return "low"
    if independent_ratio >= 0.6:
        return "high"
    if independent_ratio > 0.0 or self_ratio > 0.0:
        return "medium"
    return "low"


def _score_entry(
    score: float,
    evidence_basis: dict[str, Any],
    missing_inputs: list[str],
    risk: str,
    independent_ratio: float,
    self_ratio: float,
) -> dict[str, Any]:
    return {
        "score": round(float(score), 2),
        "evidence_basis": evidence_basis,
        "missing_inputs": missing_inputs,
        "confidence_level": _confidence(missing_inputs, independent_ratio, self_ratio),
        "known_false_confidence_risk": risk,
    }


def build_report(runtime_evidence_path: Path | None) -> dict[str, Any]:
    src = _read_inputs()
    inv_doc = src["invariants"] or {}
    invariants = inv_doc.get("invariants", [])
    debt_categories = inv_doc.get("governance_debt_categories", DEBT_CATEGORIES)

    total_invariants = len(invariants)
    with_check = 0
    with_evidence_requirements = 0
    gate_linked = 0
    rollback_linked = 0
    verifier_linked = 0
    provenance_linked = 0
    blast_linked = 0
    anti_theater_linked = 0

    for inv in invariants:
        v = inv.get("verification", {}) or {}
        evidence_required = v.get("evidence_required", []) or []
        if v.get("check_hook"):
            with_check += 1
        if evidence_required:
            with_evidence_requirements += 1

        req_set = set(evidence_required)
        inv_id = str(inv.get("id", ""))
        if "gate_id" in req_set or "gate_record_id" in req_set:
            gate_linked += 1
        if inv_id.startswith("INV-ROLLBACK") or {"rollback_run_id", "recovery_state_hash"}.issubset(req_set):
            rollback_linked += 1
        if "verifier_id" in req_set or "verifier_result" in req_set:
            verifier_linked += 1
        if "source_sha256" in req_set or "source_artifact_uri" in req_set:
            provenance_linked += 1
        if "blast_radius_score" in req_set:
            blast_linked += 1
        if inv_id.startswith("INV-THEATER") or "anti_theater_risks" in req_set:
            anti_theater_linked += 1

    schema = src["evidence_schema"]
    top_required = schema.get("required", [])
    record_required = schema.get("properties", {}).get("records", {}).get("items", {}).get("required", [])
    provenance_required = (
        schema.get("properties", {})
        .get("records", {})
        .get("items", {})
        .get("properties", {})
        .get("provenance", {})
        .get("required", [])
    )

    runtime_records = _parse_runtime_jsonl(runtime_evidence_path)
    runtime_schema_required = set(src["runtime_schema"].get("required", []))

    independent_count = 0
    self_attested_count = 0
    runtime_complete_count = 0
    runtime_gate_count = 0
    runtime_rollback_count = 0
    runtime_verifier_count = 0
    runtime_prov_complete_count = 0
    runtime_invariant_hits: set[str] = set()

    for rec in runtime_records:
        keys = set(rec.keys())
        if runtime_schema_required.issubset(keys):
            runtime_complete_count += 1
        transition_type = rec.get("transition_type")
        if transition_type in {"deploy", "migrate", "rollback", "reconcile", "retry_reentry"}:
            runtime_gate_count += 1
        if transition_type == "rollback":
            runtime_rollback_count += 1
        if transition_type == "verifier_result":
            runtime_verifier_count += 1

        independent_ref = rec.get("independent_verifier_ref")
        self_attested = bool(rec.get("self_attested"))
        if independent_ref:
            independent_count += 1
        if self_attested:
            self_attested_count += 1

        if rec.get("artifact_digest") and rec.get("raw_log_refs") and rec.get("source_commit_sha"):
            runtime_prov_complete_count += 1

        for item in rec.get("invariant_results", []) or []:
            iid = item.get("invariant_id")
            if iid:
                runtime_invariant_hits.add(iid)

    total_runtime = len(runtime_records)
    independent_ratio = 0.0 if total_runtime == 0 else independent_count / total_runtime
    self_ratio = 0.0 if total_runtime == 0 else self_attested_count / total_runtime

    risk_flags = []
    if "append-only" not in src["anti_md"].lower():
        risk_flags.append("missing_append_only_provenance_control")
    if total_runtime == 0:
        risk_flags.append("missing_runtime_evidence")
    if independent_count == 0 and total_runtime > 0:
        risk_flags.append("no_independent_verification_in_runtime_feed")
    if self_attested_count > independent_count:
        risk_flags.append("self_attestation_dominates_runtime_feed")

    missing_runtime_inputs = []
    if total_runtime == 0:
        missing_runtime_inputs = [
            "runtime_evidence_records",
            "runtime_gate_transition_events",
            "runtime_rollback_events",
            "runtime_verifier_results",
            "runtime_provenance_observations",
        ]

    artifact_metrics = {
        "invariant_coverage": {"num": with_check, "den": total_invariants, "pct": _pct(with_check, total_invariants)},
        "gate_coverage": {"num": gate_linked, "den": total_invariants, "pct": _pct(gate_linked, total_invariants)},
        "rollback_proof_coverage": {"num": rollback_linked, "den": total_invariants, "pct": _pct(rollback_linked, total_invariants)},
        "verifier_coverage": {"num": verifier_linked, "den": total_invariants, "pct": _pct(verifier_linked, total_invariants)},
        "provenance_completeness": {
            "num": provenance_linked,
            "den": total_invariants,
            "pct": _pct(provenance_linked, total_invariants),
            "schema_required_provenance_fields": provenance_required,
        },
        "evidence_completeness": {
            "num": with_evidence_requirements,
            "den": total_invariants,
            "pct": _pct(with_evidence_requirements, total_invariants),
            "schema_required_top_level_fields": top_required,
            "schema_required_record_fields": record_required,
        },
        "trust_primitive_maturity": {
            "num": len(inv_doc.get("trust_boundaries", [])),
            "den": 5,
            "pct": _pct(len(inv_doc.get("trust_boundaries", [])), 5),
        },
    }

    runtime_metrics = {
        "runtime_records_present": total_runtime,
        "runtime_record_schema_completeness": {"num": runtime_complete_count, "den": total_runtime, "pct": _pct(runtime_complete_count, total_runtime)},
        "runtime_gate_coverage": {"num": runtime_gate_count, "den": total_runtime, "pct": _pct(runtime_gate_count, total_runtime)},
        "runtime_rollback_coverage": {"num": runtime_rollback_count, "den": total_runtime, "pct": _pct(runtime_rollback_count, total_runtime)},
        "runtime_verifier_coverage": {"num": runtime_verifier_count, "den": total_runtime, "pct": _pct(runtime_verifier_count, total_runtime)},
        "runtime_provenance_completeness": {"num": runtime_prov_complete_count, "den": total_runtime, "pct": _pct(runtime_prov_complete_count, total_runtime)},
        "runtime_invariant_coverage": {"num": len(runtime_invariant_hits), "den": total_invariants, "pct": _pct(len(runtime_invariant_hits), total_invariants)},
        "confidence_sources": {
            "independent_verified_records": independent_count,
            "self_attested_records": self_attested_count,
            "independent_ratio": round(independent_ratio, 4),
            "self_attested_ratio": round(self_ratio, 4),
        },
        "missing_runtime_evidence": missing_runtime_inputs,
    }

    rollback_score = round((artifact_metrics["rollback_proof_coverage"]["pct"] * 0.5) + (runtime_metrics["runtime_rollback_coverage"]["pct"] * 0.5), 2)
    provenance_score = round((artifact_metrics["provenance_completeness"]["pct"] * 0.4) + (runtime_metrics["runtime_provenance_completeness"]["pct"] * 0.6), 2)
    verifier_score = round((artifact_metrics["verifier_coverage"]["pct"] * 0.4) + (runtime_metrics["runtime_verifier_coverage"]["pct"] * 0.6), 2)
    invariant_score = round((artifact_metrics["invariant_coverage"]["pct"] * 0.6) + (runtime_metrics["runtime_invariant_coverage"]["pct"] * 0.4), 2)
    blast_score = round((artifact_metrics["gate_coverage"]["pct"] * 0.5) + (runtime_metrics["runtime_gate_coverage"]["pct"] * 0.5), 2)
    integrity_score = round((rollback_score + provenance_score + verifier_score + invariant_score + blast_score) / 5.0, 2)

    anti_theater_risk = round(
        100.0
        - (
            (runtime_metrics["runtime_record_schema_completeness"]["pct"] * 0.3)
            + (runtime_metrics["runtime_provenance_completeness"]["pct"] * 0.3)
            + (runtime_metrics["confidence_sources"]["independent_ratio"] * 100.0 * 0.4)
        ),
        2,
    )

    score_vectors = {
        "rollback_trust_maturity": _score_entry(
            rollback_score,
            {"artifact": artifact_metrics["rollback_proof_coverage"], "runtime": runtime_metrics["runtime_rollback_coverage"]},
            missing_runtime_inputs,
            "rollback confidence remains capped without independent rollback verification",
            independent_ratio,
            self_ratio,
        ),
        "provenance_maturity": _score_entry(
            provenance_score,
            {"artifact": artifact_metrics["provenance_completeness"], "runtime": runtime_metrics["runtime_provenance_completeness"]},
            missing_runtime_inputs,
            "provenance can be overstated when records are self-attested",
            independent_ratio,
            self_ratio,
        ),
        "verifier_maturity": _score_entry(
            verifier_score,
            {"artifact": artifact_metrics["verifier_coverage"], "runtime": runtime_metrics["runtime_verifier_coverage"]},
            missing_runtime_inputs,
            "verifier maturity inflated if verifier_result exists without independent verifier refs",
            independent_ratio,
            self_ratio,
        ),
        "invariant_coverage_maturity": _score_entry(
            invariant_score,
            {"artifact": artifact_metrics["invariant_coverage"], "runtime": runtime_metrics["runtime_invariant_coverage"]},
            missing_runtime_inputs,
            "invariant checks may be shallow despite full artifact coverage",
            independent_ratio,
            self_ratio,
        ),
        "blast_radius_maturity": _score_entry(
            blast_score,
            {"artifact": artifact_metrics["gate_coverage"], "runtime": runtime_metrics["runtime_gate_coverage"]},
            missing_runtime_inputs,
            "blast-radius maturity is approximate until explicit blast score records are ingested",
            independent_ratio,
            self_ratio,
        ),
        "governance_integrity_maturity": _score_entry(
            integrity_score,
            {
                "decomposed": {
                    "rollback_trust_maturity": rollback_score,
                    "provenance_maturity": provenance_score,
                    "verifier_maturity": verifier_score,
                    "invariant_coverage_maturity": invariant_score,
                    "blast_radius_maturity": blast_score,
                }
            },
            missing_runtime_inputs,
            "integrity can appear healthy while independent verification is sparse",
            independent_ratio,
            self_ratio,
        ),
        "anti_theater_risk": _score_entry(
            anti_theater_risk,
            {
                "artifact": {"anti_theater_invariant_links": {"num": anti_theater_linked, "den": total_invariants, "pct": _pct(anti_theater_linked, total_invariants)}},
                "runtime": {
                    "runtime_record_schema_completeness": runtime_metrics["runtime_record_schema_completeness"]["pct"],
                    "runtime_provenance_completeness": runtime_metrics["runtime_provenance_completeness"]["pct"],
                    "independent_ratio": runtime_metrics["confidence_sources"]["independent_ratio"],
                },
            },
            missing_runtime_inputs,
            "self-attested dominant evidence can suppress detectable theater while confidence remains weak",
            independent_ratio,
            self_ratio,
        ),
    }

    # Cap confidence on all scores if no independent verification evidence exists.
    if independent_count == 0:
        for v in score_vectors.values():
            v["confidence_level"] = "low"

    debt_counts = {c: 0 for c in debt_categories}
    for rec in runtime_records:
        reasons = set(rec.get("reason_codes", []) or [])
        if rec.get("transition_type") in {"deploy", "migrate", "rollback", "reconcile", "retry_reentry"} and not rec.get("correlation_id"):
            debt_counts["ungated_transitions"] += 1
        if not rec.get("independent_verifier_ref"):
            debt_counts["unverifiable_claims"] += 1
        if not rec.get("artifact_digest") or not rec.get("raw_log_refs"):
            debt_counts["missing_provenance"] += 1
        if rec.get("transition_type") == "rollback" and not rec.get("independent_verifier_ref"):
            debt_counts["missing_rollback_proof"] += 1
        if rec.get("transition_type") == "verifier_result" and rec.get("evidence_strength") == "weak":
            debt_counts["detector_blind_spots"] += 1
        if rec.get("evidence_source_type") == "manual_attestation":
            debt_counts["heuristic_when_deterministic_possible"] += 1
        if rec.get("transition_type") == "break_glass_event":
            debt_counts["unsafe_autonomous_execution_surfaces"] += 1
        if "detector_blind_spot" in reasons:
            debt_counts["detector_blind_spots"] += 1

    governance_debt = {
        c: {
            "count": debt_counts.get(c, 0),
            "basis": "runtime evidence ingest" if total_runtime > 0 else "docs-only stub cannot observe runtime incidents",
            "confidence_level": "medium" if total_runtime > 0 else "low",
            "missing_inputs": missing_runtime_inputs,
        }
        for c in debt_categories
    }

    report = {
        "report_version": "v0-stub-runtime-ingest",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "mode": "score_only_non_enforcing",
        "input_files": {k: str(v.relative_to(ROOT)) for k, v in INPUTS.items()},
        "runtime_evidence_file": str(runtime_evidence_path.relative_to(ROOT)) if runtime_evidence_path and runtime_evidence_path.exists() else None,
        "coverage": {
            "artifact_structure": artifact_metrics,
            "runtime_evidence": runtime_metrics,
        },
        "score_vectors": score_vectors,
        "governance_debt": governance_debt,
        "anti_theater_flags": {
            "low_confidence_required_when_missing_or_unverifiable": True,
            "self_attestation_weaker_than_independent_verification": True,
            "runtime_evidence_missing": total_runtime == 0,
            "risk_flags": risk_flags,
        },
        "known_limitations": [
            "No gate enforcement/block behavior in this scorer pass.",
            "Schema validation is lightweight; full JSON Schema runtime validator not embedded.",
            "Debt heuristics are intentionally simple and may undercount nuanced incidents.",
            "Confidence can improve with runtime feed but remains capped if independent evidence is sparse.",
        ],
    }
    return report


def render_md(report: dict[str, Any]) -> str:
    lines = ["# Latest Governance Score (Deterministic Stub + Runtime Ingest)", ""]
    lines.append(f"- Generated UTC: `{report['generated_at_utc']}`")
    lines.append(f"- Mode: `{report['mode']}`")
    lines.append(f"- Runtime evidence file: `{report['runtime_evidence_file']}`")
    lines.append("")
    lines.append("## Artifact-Structure Coverage")
    for k, v in report["coverage"]["artifact_structure"].items():
        if isinstance(v, dict) and "pct" in v:
            lines.append(f"- {k}: {v['num']}/{v['den']} ({v['pct']}%)")
    lines.append("")
    lines.append("## Runtime-Evidence Coverage")
    rm = report["coverage"]["runtime_evidence"]
    lines.append(f"- runtime_records_present: {rm['runtime_records_present']}")
    for k, v in rm.items():
        if isinstance(v, dict) and "pct" in v:
            lines.append(f"- {k}: {v['num']}/{v['den']} ({v['pct']}%)")
    cs = rm["confidence_sources"]
    lines.append(f"- independent_verified_records: {cs['independent_verified_records']}")
    lines.append(f"- self_attested_records: {cs['self_attested_records']}")
    lines.append(f"- independent_ratio: {cs['independent_ratio']}")
    lines.append(f"- self_attested_ratio: {cs['self_attested_ratio']}")
    lines.append(f"- missing_runtime_evidence: {rm['missing_runtime_evidence']}")
    lines.append("")
    lines.append("## Vector Scores")
    for k, v in report["score_vectors"].items():
        lines.append(f"- {k}")
        lines.append(f"  - score: {v['score']}")
        lines.append(f"  - confidence_level: {v['confidence_level']}")
        lines.append(f"  - missing_inputs: {', '.join(v['missing_inputs']) if v['missing_inputs'] else 'none'}")
        lines.append(f"  - known_false_confidence_risk: {v['known_false_confidence_risk']}")
    lines.append("")
    lines.append("## Governance Debt")
    for k, v in report["governance_debt"].items():
        lines.append(f"- {k}: count={v['count']} (confidence={v['confidence_level']})")
    lines.append("")
    lines.append("## Anti-Theater Flags")
    for k, v in report["anti_theater_flags"].items():
        lines.append(f"- {k}: {v}")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime-evidence", default=str(DEFAULT_RUNTIME_EVIDENCE), help="Path to runtime evidence JSONL")
    args = parser.parse_args()

    runtime_path = Path(args.runtime_evidence).resolve() if args.runtime_evidence else None
    REPORTS.mkdir(parents=True, exist_ok=True)
    report = build_report(runtime_path)
    json_path = REPORTS / "latest_governance_score.json"
    md_path = REPORTS / "latest_governance_score.md"
    json_path.write_text(json.dumps(report, indent=2) + "\n")
    md_path.write_text(render_md(report))
    print(str(json_path.relative_to(ROOT)))
    print(str(md_path.relative_to(ROOT)))


if __name__ == "__main__":
    main()
