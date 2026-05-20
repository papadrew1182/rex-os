# Trust Boundaries v0

## Boundary Taxonomy (authoritative)

1. `deterministic_truth`
- Definition: Outcome reproducibly derived from deterministic checks.
- Allowed autonomy: safe_autonomous, bounded_autonomous.

2. `independently_verified_truth`
- Definition: Outcome confirmed by independent verifier or orthogonal evidence source.
- Allowed autonomy: safe_autonomous, bounded_autonomous.

3. `heuristic_interpretation`
- Definition: Outcome inferred from heuristics or partial signals.
- Allowed autonomy: bounded_autonomous, autonomous_with_human_attestation_required.

4. `human_authoritative_override`
- Definition: Human decision explicitly overrides automated signal.
- Allowed autonomy: autonomous_with_human_attestation_required.

5. `unverifiable_state`
- Definition: No deterministic or independent verification currently possible.
- Allowed autonomy: autonomous_with_human_attestation_required; forbidden for high-blast-radius actions.

## Mapping Rule
Every gate decision must include:
- trust_boundary
- autonomy_safety_level
- justification
- evidence_ids[]

## Maturity Link
Trust primitive maturity score is derived from percentage of gate decisions mapped to deterministic or independently verified boundaries, weighted by blast radius.

## Known Theater Risks
- Inflated-confidence risk: classifying heuristic signals as deterministic.
- Shallow verification risk: labeling independent verification when sources are not actually independent.
- Immature detector risk: detector quality unknown but used to claim verified truth.
- Unverifiable trust assumption: treating unverifiable state as low risk by default.
- Governance sophistication outrunning operational maturity: elaborate boundary labels with inconsistent usage.
