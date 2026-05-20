# Rollback Rehearsal Program v0

## Objective
Continuously prove rollback truth with deterministic evidence and bounded blast radius.

## Cadence
- Weekly minimum for active release train.
- Additional rehearsal before any autonomy scope expansion.

## Required Evidence Per Rehearsal
- rehearsal_id
- target_sha
- rollback_target_sha (LKG)
- pre_state_hash
- post_rollback_state_hash
- recovery_verification_result
- artifacts_uri

## Compliance Rule
Rollback rehearsal compliance = passed_rehearsals_with_full_evidence / required_rehearsals_in_window.

## Maturity Primitive Hook
```yaml
rollback_trust_maturity_inputs:
  rollback_rehearsal_pass_rate: "0..1"
  rollback_proof_completeness: "0..1"
  rollback_recovery_determinism: "0..1"
```

## Guardrails
- No claim of "safe autonomous" for high-blast-radius transitions if latest rehearsal is stale or failed.
- Missing rollback proof adds governance debt: `missing_rollback_proof`.

## Known Theater Risks
- Inflated-confidence risk: declaring rollback readiness from historical runs only.
- Shallow verification risk: rollback command success without post-rollback functional verification.
- Immature detector risk: no detector for hidden data drift after rollback.
- Unverifiable trust assumption: trusting manual operator report over artifact hashes.
- Governance sophistication outrunning operational maturity: rehearsal checklist grows while execution reliability stays low.
