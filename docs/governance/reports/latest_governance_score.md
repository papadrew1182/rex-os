# Latest Governance Score (Deterministic Stub)

- Generated UTC: `2026-05-20T03:09:47.137786+00:00`
- Mode: `score_only_non_enforcing`

## Coverage Metrics
- invariant_coverage: 6/6 (100.0%)
- gate_coverage: 2/6 (33.33%)
- rollback_proof_coverage: 1/6 (16.67%)
- verifier_coverage: 1/6 (16.67%)
- provenance_completeness: 1/6 (16.67%)
- evidence_completeness: 6/6 (100.0%)
- trust_primitive_maturity: 5/5 (100.0%)

## Vector Scores
- rollback_trust_maturity
  - score: 16.67
  - confidence_level: low
  - missing_inputs: evidence_ledger_runtime_records, gate_transition_events, rollback_rehearsal_run_artifacts, verifier_execution_results, provenance_artifact_hash_observations
  - known_false_confidence_risk: rollback maturity is artifact-linked, not execution-proven in this stub
- provenance_maturity
  - score: 16.67
  - confidence_level: low
  - missing_inputs: evidence_ledger_runtime_records, gate_transition_events, rollback_rehearsal_run_artifacts, verifier_execution_results, provenance_artifact_hash_observations
  - known_false_confidence_risk: provenance references exist, but runtime artifact verification is not observed
- verifier_maturity
  - score: 16.67
  - confidence_level: low
  - missing_inputs: evidence_ledger_runtime_records, gate_transition_events, rollback_rehearsal_run_artifacts, verifier_execution_results, provenance_artifact_hash_observations
  - known_false_confidence_risk: verifier fields are declared, not validated from real verifier executions
- invariant_coverage_maturity
  - score: 100.0
  - confidence_level: medium
  - missing_inputs: none
  - known_false_confidence_risk: high score here can still hide shallow checks
- blast_radius_maturity
  - score: 16.67
  - confidence_level: low
  - missing_inputs: evidence_ledger_runtime_records, gate_transition_events, rollback_rehearsal_run_artifacts, verifier_execution_results, provenance_artifact_hash_observations
  - known_false_confidence_risk: blast-radius scoring exists in artifacts but no runtime blast-radius evidence feed
- governance_integrity_maturity
  - score: 62.5
  - confidence_level: low
  - missing_inputs: evidence_ledger_runtime_records, gate_transition_events, rollback_rehearsal_run_artifacts, verifier_execution_results, provenance_artifact_hash_observations
  - known_false_confidence_risk: integrity score can be inflated without independent runtime evidence
- anti_theater_risk
  - score: 83.33
  - confidence_level: low
  - missing_inputs: evidence_ledger_runtime_records, gate_transition_events, rollback_rehearsal_run_artifacts, verifier_execution_results, provenance_artifact_hash_observations
  - known_false_confidence_risk: low anti-theater risk score can be false if evidence remains self-attested or unverifiable

## Governance Debt (explicit categories)
- ungated_transitions: count=0 (confidence=low)
- unverifiable_claims: count=0 (confidence=low)
- missing_provenance: count=0 (confidence=low)
- missing_rollback_proof: count=0 (confidence=low)
- detector_blind_spots: count=0 (confidence=low)
- heuristic_when_deterministic_possible: count=0 (confidence=low)
- unsafe_autonomous_execution_surfaces: count=0 (confidence=low)

## Anti-Theater Flags
- low_confidence_required_when_missing_or_unverifiable: True
- runtime_evidence_missing: True
- risk_flags: []
- high_false_confidence_risk: True

## Known Limitations
- No runtime evidence ledger dataset is consumed in this stub.
- No deploy/runtime behavior is blocked or mutated by this scorer.
- Scores are structural/readiness indicators and may overstate operational maturity.
