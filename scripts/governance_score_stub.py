#!/usr/bin/env python3
"""Minimal deterministic governance scorer stub (non-enforcing).

Reads governance artifacts and emits:
- docs/governance/reports/latest_governance_score.json
- docs/governance/reports/latest_governance_score.md
"""

from __future__ import annotations

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
}

DEBT_CATEGORIES = [
    "ungated_transitions",
    "unverifiable_claims",
    "missing_provenance",
    "missing_rollback_proof",
    "detector_blind_spots",
    "heuristic_when_deterministic_possible",
    "unsafe_autonomous_execution_surfaces",
]


def _read_inputs() -> dict[str, Any]:
    missing = [k for k, p in INPUTS.items() if not p.exists()]
    if missing:
        raise FileNotFoundError(f"Missing required governance artifacts: {missing}")

    invariants = yaml.safe_load(INPUTS["invariants"].read_text())
    evidence_schema = json.loads(INPUTS["evidence_schema"].read_text())
    policy_md = INPUTS["policy"].read_text()
    trust_md = INPUTS["trust"].read_text()
    anti_md = INPUTS["anti_theater"].read_text()
    return {
        "invariants": invariants,
        "evidence_schema": evidence_schema,
        "policy_md": policy_md,
        "trust_md": trust_md,
        "anti_md": anti_md,
    }


def _pct(num: int, den: int) -> float:
    return 0.0 if den <= 0 else round((num / den) * 100.0, 2)


def _confidence(missing_inputs: list[str], risk_flags: list[str]) -> str:
    if missing_inputs:
        return "low"
    if risk_flags:
        return "medium"
    return "high"


def _score_entry(score: float, evidence_basis: dict[str, Any], missing_inputs: list[str], risk: str) -> dict[str, Any]:
    return {
        "score": round(float(score), 2),
        "evidence_basis": evidence_basis,
        "missing_inputs": missing_inputs,
        "confidence_level": _confidence(missing_inputs, [risk] if risk else []),
        "known_false_confidence_risk": risk,
    }


def build_report() -> dict[str, Any]:
    src = _read_inputs()
    inv_doc = src["invariants"] or {}
    invariants = inv_doc.get("invariants", [])
    debt_categories = inv_doc.get("governance_debt_categories", DEBT_CATEGORIES)

    # Structural coverage from artifacts only (no runtime ledger in this stub).
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

    # Parse schema-required keys for evidence/provenance completeness expectations.
    schema = src["evidence_schema"]
    top_required = schema.get("required", [])
    record_required = (
        schema.get("properties", {})
        .get("records", {})
        .get("items", {})
        .get("required", [])
    )
    provenance_required = (
        schema.get("properties", {})
        .get("records", {})
        .get("items", {})
        .get("properties", {})
        .get("provenance", {})
        .get("required", [])
    )

    # Detect shallow/self-attested/unverifiable conditions from docs-only pass.
    risk_flags = []
    if "append-only" not in src["anti_md"].lower():
        risk_flags.append("missing_append_only_provenance_control")
    if "independent" not in src["trust_md"].lower():
        risk_flags.append("missing_independent_verification_language")
    if "deterministic" not in src["policy_md"].lower():
        risk_flags.append("missing_deterministic_policy_language")

    missing_runtime_inputs = [
        "evidence_ledger_runtime_records",
        "gate_transition_events",
        "rollback_rehearsal_run_artifacts",
        "verifier_execution_results",
        "provenance_artifact_hash_observations",
    ]

    metric_rollup = {
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

    # Vector scores: deterministic + decomposed + confidence-aware.
    score_vectors = {
        "rollback_trust_maturity": _score_entry(
            metric_rollup["rollback_proof_coverage"]["pct"],
            {"invariant_links": metric_rollup["rollback_proof_coverage"]},
            missing_runtime_inputs,
            "rollback maturity is artifact-linked, not execution-proven in this stub",
        ),
        "provenance_maturity": _score_entry(
            metric_rollup["provenance_completeness"]["pct"],
            {"invariant_links": metric_rollup["provenance_completeness"]},
            missing_runtime_inputs,
            "provenance references exist, but runtime artifact verification is not observed",
        ),
        "verifier_maturity": _score_entry(
            metric_rollup["verifier_coverage"]["pct"],
            {"invariant_links": metric_rollup["verifier_coverage"]},
            missing_runtime_inputs,
            "verifier fields are declared, not validated from real verifier executions",
        ),
        "invariant_coverage_maturity": _score_entry(
            metric_rollup["invariant_coverage"]["pct"],
            {"invariant_links": metric_rollup["invariant_coverage"]},
            [],
            "high score here can still hide shallow checks",
        ),
        "blast_radius_maturity": _score_entry(
            _pct(blast_linked, total_invariants),
            {"invariant_links": {"num": blast_linked, "den": total_invariants, "pct": _pct(blast_linked, total_invariants)}},
            missing_runtime_inputs,
            "blast-radius scoring exists in artifacts but no runtime blast-radius evidence feed",
        ),
        "governance_integrity_maturity": _score_entry(
            round(
                (
                    metric_rollup["invariant_coverage"]["pct"]
                    + metric_rollup["evidence_completeness"]["pct"]
                    + metric_rollup["gate_coverage"]["pct"]
                    + metric_rollup["provenance_completeness"]["pct"]
                )
                / 4.0,
                2,
            ),
            {
                "decomposed_inputs": {
                    "invariant_coverage_pct": metric_rollup["invariant_coverage"]["pct"],
                    "evidence_completeness_pct": metric_rollup["evidence_completeness"]["pct"],
                    "gate_coverage_pct": metric_rollup["gate_coverage"]["pct"],
                    "provenance_completeness_pct": metric_rollup["provenance_completeness"]["pct"],
                }
            },
            missing_runtime_inputs,
            "integrity score can be inflated without independent runtime evidence",
        ),
        "anti_theater_risk": _score_entry(
            round(100.0 - _pct(anti_theater_linked, total_invariants), 2),
            {
                "risk_flags": risk_flags,
                "anti_theater_invariant_links": {"num": anti_theater_linked, "den": total_invariants, "pct": _pct(anti_theater_linked, total_invariants)},
            },
            missing_runtime_inputs,
            "low anti-theater risk score can be false if evidence remains self-attested or unverifiable",
        ),
    }

    # Debt: explicit categories + deterministic current-state disclosure.
    debt = {
        c: {
            "count": 0,
            "basis": "docs-only stub cannot observe runtime incidents; count defaults to 0 with low confidence",
            "confidence_level": "low",
            "missing_inputs": missing_runtime_inputs,
        }
        for c in debt_categories
    }

    report = {
        "report_version": "v0-stub",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "mode": "score_only_non_enforcing",
        "input_files": {k: str(v.relative_to(ROOT)) for k, v in INPUTS.items()},
        "metrics": metric_rollup,
        "score_vectors": score_vectors,
        "governance_debt": debt,
        "anti_theater_flags": {
            "low_confidence_required_when_missing_or_unverifiable": True,
            "runtime_evidence_missing": True,
            "risk_flags": risk_flags,
            "high_false_confidence_risk": True,
        },
        "known_limitations": [
            "No runtime evidence ledger dataset is consumed in this stub.",
            "No deploy/runtime behavior is blocked or mutated by this scorer.",
            "Scores are structural/readiness indicators and may overstate operational maturity.",
        ],
    }
    return report


def render_md(report: dict[str, Any]) -> str:
    lines = []
    lines.append("# Latest Governance Score (Deterministic Stub)")
    lines.append("")
    lines.append(f"- Generated UTC: `{report['generated_at_utc']}`")
    lines.append(f"- Mode: `{report['mode']}`")
    lines.append("")
    lines.append("## Coverage Metrics")
    for k, v in report["metrics"].items():
        if isinstance(v, dict) and "pct" in v:
            lines.append(f"- {k}: {v['num']}/{v['den']} ({v['pct']}%)")
    lines.append("")
    lines.append("## Vector Scores")
    for k, v in report["score_vectors"].items():
        lines.append(f"- {k}")
        lines.append(f"  - score: {v['score']}")
        lines.append(f"  - confidence_level: {v['confidence_level']}")
        lines.append(f"  - missing_inputs: {', '.join(v['missing_inputs']) if v['missing_inputs'] else 'none'}")
        lines.append(f"  - known_false_confidence_risk: {v['known_false_confidence_risk']}")
    lines.append("")
    lines.append("## Governance Debt (explicit categories)")
    for k, v in report["governance_debt"].items():
        lines.append(f"- {k}: count={v['count']} (confidence={v['confidence_level']})")
    lines.append("")
    lines.append("## Anti-Theater Flags")
    for k, v in report["anti_theater_flags"].items():
        lines.append(f"- {k}: {v}")
    lines.append("")
    lines.append("## Known Limitations")
    for item in report["known_limitations"]:
        lines.append(f"- {item}")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    REPORTS.mkdir(parents=True, exist_ok=True)
    report = build_report()
    json_path = REPORTS / "latest_governance_score.json"
    md_path = REPORTS / "latest_governance_score.md"
    json_path.write_text(json.dumps(report, indent=2) + "\n")
    md_path.write_text(render_md(report))
    print(str(json_path.relative_to(ROOT)))
    print(str(md_path.relative_to(ROOT)))


if __name__ == "__main__":
    main()
