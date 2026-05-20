# Anti-Theater Rules v0

## Purpose
Prevent governance theater by forcing claims to remain evidence-bound, deterministic where possible, and explicit about uncertainty.

## Non-Negotiable Rules
1. No confidence claims without evidence IDs.
2. No gate pass claim without verifier result.
3. No autonomy scope expansion while governance integrity maturity < 50.
4. Heuristic decisions must create debt item `heuristic_when_deterministic_possible` unless deterministic check is infeasible and documented.
5. Unverifiable claims must be explicitly labeled and counted.

## Anti-Fabrication Controls
- Require provenance tuple for each claim: (source_uri, source_sha256, collector).
- Disallow mutation of prior evidence records without append-only correction entry.
- Require explicit "unknown" state over inferred pass when evidence missing.

## Compliance Hooks
```yaml
anti_theater_compliance:
  required_sections:
    - known_theater_risks
    - unresolved_implementation_risks
    - weak_trust_assumptions
  hard_fail_conditions:
    - fabricated_or_missing_provenance
    - inflated_confidence_without_evidence
```

## Known Theater Risks
- Inflated-confidence risk: maturity uplift narratives unsupported by fresh evidence.
- Shallow verification risk: claims based on smoke-only checks for deep invariants.
- Immature detector risk: detector status treated as assurance without quality metrics.
- Unverifiable trust assumption: hidden dependencies accepted as stable without proof.
- Governance sophistication outrunning operational maturity: policy language becomes richer than execution evidence discipline.
