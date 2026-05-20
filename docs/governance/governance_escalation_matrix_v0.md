# Governance Escalation Matrix v0

## Trigger Classes
- Gate failure
- Missing rollback proof
- Missing provenance for high-impact claim
- Unsafe autonomous execution surface detected
- Detector blind spot on critical path

## Escalation Matrix

- Severity S0 (Critical)
  - Criteria: ungated transition, failed rollback rehearsal on active release path, forbidden autonomous action attempted.
  - Autonomy: forbidden autonomous action.
  - Required response: immediate block, rollback or freeze, human-authoritative override required.

- Severity S1 (High)
  - Criteria: missing rollback proof on high-blast-radius change, verifier coverage gap on critical gate.
  - Autonomy: autonomous with human attestation required.
  - Required response: block progression until attested mitigation and deterministic evidence.

- Severity S2 (Medium)
  - Criteria: missing provenance on non-critical claims, detector blind spots with compensating controls.
  - Autonomy: bounded autonomous.
  - Required response: proceed only with debt ticket + due date.

- Severity S3 (Low)
  - Criteria: documentation incompleteness with no gate impact.
  - Autonomy: safe autonomous.
  - Required response: fix in next cadence window.

## Machine-Readable Hook
```yaml
escalation_policy:
  severity_to_action:
    S0: block_and_freeze
    S1: block_until_attested
    S2: proceed_with_debt
    S3: proceed
```

## Known Theater Risks
- Inflated-confidence risk: severity downgraded without new evidence.
- Shallow verification risk: escalation cleared based on narrative summary only.
- Immature detector risk: detector blind spot marked "non-critical" without impact analysis.
- Unverifiable trust assumption: attestation accepted without artifact linkage.
- Governance sophistication outrunning operational maturity: complex severity taxonomy with weak enforcement discipline.
