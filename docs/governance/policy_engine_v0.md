# Rex Governance Policy Engine v0

## Objective
Provide low-complexity, deterministic, inspectable policy checks for reconciliation cadence jobs.

## Trust Boundary Classes (required on every policy decision)
- `deterministic_truth`
- `independently_verified_truth`
- `heuristic_interpretation`
- `human_authoritative_override`
- `unverifiable_state`

## Autonomy Safety Levels
- `safe_autonomous`
- `bounded_autonomous`
- `autonomous_with_human_attestation_required`
- `forbidden_autonomous_action`

## Evaluation Pipeline (in order)
1. Load invariants from `invariants_v0.yaml`.
2. Load evidence objects validated against `evidence_ledger_v0_schema.json`.
3. Evaluate gate compliance, rollback rehearsal compliance, verifier coverage, provenance completeness.
4. Compute maturity primitive scores (0-100).
5. Compute governance debt by category.
6. Emit decision:
   - proceed
   - proceed_with_attestation
   - block

## Deterministic Scoring Primitives

```yaml
maturity_scoring:
  rollback_trust_maturity:
    formula: "min(100, 40*rollback_rehearsal_pass_rate + 30*rollback_proof_completeness + 30*rollback_recovery_determinism)"
  provenance_maturity:
    formula: "min(100, 60*provenance_completeness + 40*provenance_verifiability_rate)"
  verifier_maturity:
    formula: "min(100, 70*critical_verifier_coverage + 30*verifier_consistency_rate)"
  invariant_coverage_maturity:
    formula: "min(100, 100*(invariants_with_checks / total_invariants))"
  blast_radius_maturity:
    formula: "min(100, 50*blast_radius_precheck_coverage + 50*blast_radius_policy_adherence)"
  governance_integrity_maturity:
    formula: "min(100, 25*gate_compliance + 20*evidence_completeness + 20*provenance_completeness + 20*rollback_rehearsal_compliance + 15*anti_theater_compliance)"
```

## Governance Debt Categories (required output fields)
- ungated_transitions
- unverifiable_claims
- missing_provenance
- missing_rollback_proof
- detector_blind_spots
- heuristic_when_deterministic_possible
- unsafe_autonomous_execution_surfaces

## Minimal Decision Rules
- If `ungated_transitions > 0`: `block`.
- If `missing_rollback_proof > 0` and action blast radius is high: `block`.
- If trust boundary is `unverifiable_state`: only `autonomous_with_human_attestation_required` or stricter.
- If `governance_integrity_maturity < 50`: no new autonomous scope expansion.

## Machine-Readable Output Contract
```json
{
  "decision": "proceed|proceed_with_attestation|block",
  "scores": {
    "rollback_trust_maturity": 0,
    "provenance_maturity": 0,
    "verifier_maturity": 0,
    "invariant_coverage_maturity": 0,
    "blast_radius_maturity": 0,
    "governance_integrity_maturity": 0
  },
  "debt": {
    "ungated_transitions": 0,
    "unverifiable_claims": 0,
    "missing_provenance": 0,
    "missing_rollback_proof": 0,
    "detector_blind_spots": 0,
    "heuristic_when_deterministic_possible": 0,
    "unsafe_autonomous_execution_surfaces": 0
  },
  "known_theater_risks": []
}
```

## Known Theater Risks
- Inflated-confidence risk: converting subjective confidence into numeric score without deterministic evidence.
- Shallow verification risk: over-weighting unit tests while gate-level behavior is untested.
- Immature detector risk: detector outputs used in policy decisions before calibration.
- Unverifiable trust assumption: implicit trust in manual attestations with missing artifacts.
- Governance sophistication outrunning operational maturity: policy formulas present but data feed quality weak.
