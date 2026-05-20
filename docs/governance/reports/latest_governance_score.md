# Latest Governance Score (Deterministic Stub + Runtime Ingest)

- Generated UTC: `2026-05-20T03:23:43.059092+00:00`
- Mode: `score_only_non_enforcing`
- Runtime evidence file: `docs/governance/runtime/latest_runtime_evidence.jsonl`

## Artifact-Structure Coverage
- invariant_coverage: 6/6 (100.0%)
- gate_coverage: 2/6 (33.33%)
- rollback_proof_coverage: 1/6 (16.67%)
- verifier_coverage: 1/6 (16.67%)
- provenance_completeness: 1/6 (16.67%)
- evidence_completeness: 6/6 (100.0%)
- trust_primitive_maturity: 5/5 (100.0%)

## Runtime-Evidence Coverage
- runtime_records_present: 5
- runtime_record_schema_completeness: 5/5 (100.0%)
- runtime_gate_coverage: 2/5 (40.0%)
- runtime_rollback_coverage: 1/5 (20.0%)
- runtime_verifier_coverage: 1/5 (20.0%)
- runtime_provenance_completeness: 5/5 (100.0%)
- runtime_invariant_coverage: 4/6 (66.67%)
- independent_verified_records: 3
- self_attested_records: 2
- independent_ratio: 0.6
- self_attested_ratio: 0.4
- synthetic_records: 0
- synthetic_ratio: 0.0
- missing_runtime_evidence: []

## Vector Scores
- rollback_trust_maturity
  - score: 18.34
  - confidence_level: high
  - missing_inputs: none
  - known_false_confidence_risk: rollback confidence remains capped without independent rollback verification
- provenance_maturity
  - score: 66.67
  - confidence_level: high
  - missing_inputs: none
  - known_false_confidence_risk: provenance can be overstated when records are self-attested
- verifier_maturity
  - score: 18.67
  - confidence_level: high
  - missing_inputs: none
  - known_false_confidence_risk: verifier maturity inflated if verifier_result exists without independent verifier refs
- invariant_coverage_maturity
  - score: 86.67
  - confidence_level: high
  - missing_inputs: none
  - known_false_confidence_risk: invariant checks may be shallow despite full artifact coverage
- blast_radius_maturity
  - score: 36.66
  - confidence_level: high
  - missing_inputs: none
  - known_false_confidence_risk: blast-radius maturity is approximate until explicit blast score records are ingested
- governance_integrity_maturity
  - score: 45.4
  - confidence_level: high
  - missing_inputs: none
  - known_false_confidence_risk: integrity can appear healthy while independent verification is sparse
- anti_theater_risk
  - score: 16.0
  - confidence_level: high
  - missing_inputs: none
  - known_false_confidence_risk: self-attested dominant evidence can suppress detectable theater while confidence remains weak

## Governance Debt
- ungated_transitions: count=0 (confidence=medium)
- unverifiable_claims: count=2 (confidence=medium)
- missing_provenance: count=0 (confidence=medium)
- missing_rollback_proof: count=0 (confidence=medium)
- detector_blind_spots: count=0 (confidence=medium)
- heuristic_when_deterministic_possible: count=0 (confidence=medium)
- unsafe_autonomous_execution_surfaces: count=0 (confidence=medium)

## Anti-Theater Flags
- low_confidence_required_when_missing_or_unverifiable: True
- self_attestation_weaker_than_independent_verification: True
- runtime_evidence_missing: False
- risk_flags: []
