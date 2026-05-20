# Rex Governance 30-Day Implementation Plan (v0)

## Purpose
Failure-cost weighted rollout of governance controls that improve operational survivability, rollback truth, deterministic verification, bounded blast radius, and anti-fabrication trust.

## Scoring Targets (machine-scored each reconciliation run)
- Invariant coverage maturity
- Rollback trust maturity
- Provenance maturity
- Verifier maturity
- Blast-radius maturity
- Governance integrity maturity

## 30-Day Sequence (do not reorder unless blocker)

### Days 1-7 — Deterministic Minimum Viable Governance
- Ship invariants catalog (`invariants_v0.yaml`) with owners and deterministic check hooks.
- Ship evidence ledger schema (`evidence_ledger_v0_schema.json`).
- Require gate records for any phase transition.
- Start governance debt ledger updates per run.

Exit criteria:
- >=80% invariants mapped to a deterministic check or explicitly marked unverifiable.
- 100% phase transitions have gate evidence IDs.

### Days 8-14 — Rollback & Provenance Hardening
- Rollback rehearsal program active with weekly cadence and pass/fail proof.
- Provenance requirements enforced for claims in canonical docs.
- Escalation matrix active for ungated transitions / missing rollback proof.

Exit criteria:
- >=1 successful rollback rehearsal with full evidence chain.
- >=90% claims in phase summaries carry provenance links.

### Days 15-21 — Verifier and Trust Boundary Discipline
- Trust boundary tags required in reconciliation outputs.
- Verifier registry expanded for top risk surfaces.
- Detector blind spots tracked with due dates.

Exit criteria:
- >=85% verifier coverage on critical gates.
- 0 unclassified trust assumptions in gate decisions.

### Days 22-30 — Anti-Theater Enforcement
- Anti-theater checks block inflated-confidence claims.
- Governance debt trend reported with burn-down expectation.
- Mature/immature autonomy safety level decisions codified per action family.

Exit criteria:
- Governance integrity maturity >=70.
- Unverifiable claims debt category trending down week-over-week.

## Reconciliation Hook Payload (YAML/JSON emit)
```yaml
governance_reconciliation_targets:
  scoring:
    - rollback_trust_maturity
    - provenance_maturity
    - verifier_maturity
    - invariant_coverage_maturity
    - blast_radius_maturity
    - governance_integrity_maturity
  debt_categories:
    - ungated_transitions
    - unverifiable_claims
    - missing_provenance
    - missing_rollback_proof
    - detector_blind_spots
    - heuristic_when_deterministic_possible
    - unsafe_autonomous_execution_surfaces
```

## Known Theater Risks
- Inflated-confidence risk: reporting maturity increases without corresponding evidence links.
- Shallow verification risk: pass/fail reported from narrow test slices not representative of production gates.
- Immature detector risk: detector marked "active" but no backtesting accuracy evidence.
- Unverifiable trust assumption: accepting human summary statements without raw logs/artifacts.
- Governance sophistication outrunning operational maturity: introducing complex scoring before deterministic checks stabilize.
