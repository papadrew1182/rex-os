# Runtime Evidence Contract v0

## Purpose
Define a low-complexity, non-blocking runtime evidence feed for governance scoring.

This contract is for ingestion only. It does **not** enforce gates, block deploys, or change runtime transition behavior.

## Record transport
- Format: JSON Lines (`.jsonl`)
- One event per line
- UTF-8 text
- Append-only preferred

## Supported transition/event types
- `deploy`
- `migrate`
- `rollback`
- `reconcile`
- `retry_reentry`
- `verifier_result`
- `invariant_result`
- `escalation_event`
- `break_glass_event`

## Required fields per record
- `event_id`
- `timestamp_utc`
- `transition_type`
- `actor_type`
- `actor_id`
- `target_service`
- `target_env`
- `source_commit_sha`
- `artifact_digest`
- `env_fingerprint`
- `correlation_id`
- `evidence_strength`
- `evidence_source_type`
- `self_attested`
- `independent_verifier_ref`
- `raw_log_refs`
- `invariant_results`
- `decision`
- `reason_codes`
- `previous_record_hash`
- `record_hash`

## Confidence semantics
- Self-attested evidence can improve coverage metrics, but confidence is capped.
- Independently verified evidence is required for high confidence.
- Missing runtime evidence keeps confidence low, even with strong artifact structure.

## Normalization notes
- `evidence_strength` should be one of: `weak`, `medium`, `strong`.
- `evidence_source_type` should be one of: `log`, `test`, `monitor`, `manual_attestation`, `external_verifier`.
- `invariant_results` is an array of `{invariant_id, status, verifier_ref}`.
- `decision` should be one of: `proceed`, `proceed_with_attestation`, `block`, `observe_only`.

## Known Theater Risks
- Inflated-confidence risk: counting self-attested records as equivalent to independent verification.
- Shallow verification risk: many events with sparse raw logs.
- Immature detector risk: verifier_result events present without verifier reliability history.
- Unverifiable trust assumption: missing/blank independent verifier refs treated as trustworthy.
- Governance sophistication outrunning operational maturity: rich runtime schema with low-quality producer discipline.
