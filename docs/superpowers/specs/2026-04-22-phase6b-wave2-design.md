# Phase 6b Wave 2 — Financial Instrument Tools + create_decision

**Status:** approved 2026-04-22 (design brainstorm complete). Ready for implementation plan.
**Author:** Claude + Andrew Roberts.
**Parent spec:** `docs/superpowers/specs/2026-04-21-phase6-commands-approvals-design.md` (Phase 6 overall).
**Related:** `docs/superpowers/specs/2026-04-22-phase6b-wave1-design.md` (Wave 1 — established the compensator pattern).

## Goal

Extend the Phase 6 action framework with 5 more LLM tools: 4 approval-required financial-instrument creators (`create_change_event`, `create_pco`, `pay_application`, `lien_waiver`) and 1 auto-pass internal logger (`create_decision`). Rex OS INSERT only — Procore writeback is deferred to a later wave per parent spec §5 ("RFIs first, validate one month, then submittals, then the rest").

**Exit criterion:** Andrew says "flag a pending decision about which structural detail we use at grid B/4" and sees a green auto-commit card with a 60s Undo. Or he says "open a change event for the owner-change at Bishop Modern, roughly $12,000 estimated" and sees an amber approval card quoting the dollar amount and the target project. After approve, `rex.change_events` has the row; before approve, nothing has moved.

After Wave 2 ships, the registered tool count goes from 9 to 14.

## Pre-locked decisions (from 2026-04-22 brainstorm)

1. **Scope** = 5 tools. `punch_close` / `punch_reopen` deferred (blocked on `rex.punch_items` data — Phase 4 Wave 2 prereq). Inspection tools deferred (no canonical source yet).
2. **Writeback** = none. All 5 tools INSERT into Rex OS only; Procore API writebacks land in a future financial-writeback wave after the submittal-writeback wave validates in the wild.
3. **`create_decision` target** = `rex.pending_decisions` (migration 017 — no new migration needed). Semantics: "flag an open question that needs a decision." Separate from `rex.meeting_decisions` (decisions already made, requires meeting_id) — that's a future tool.
4. **Classifier for financial tools** = `fires_external_effect=True`. Triggers `requires_approval()` unconditionally regardless of dollar amount, matching Phase 6 memory §3 ("any dollar amount → approval, no exceptions"). Dollar amount still populates `financial_dollar_amount` for the card's reason-line display ("financial impact: $12,345.67").
5. **Compensators** — `create_decision` gets one (DELETE by id). The 4 financial tools do NOT get compensators, matching the `answer_rfi` precedent from Wave 1. Approval-required + external-effect tools' "undo" is a compensating action with its own approval flow, which is Phase 6c "Send correction" scope.

## Current state (verified 2026-04-22)

Demo Rex OS DB has seed data for all FK targets:
- `rex.commitments`: 5, `rex.billing_periods`: 5, `rex.prime_contracts`: 1, `rex.cost_codes`: 10, `rex.projects`: 15, `rex.companies` (vendors): populated.
- `rex.change_events`: 3, `rex.payment_applications`: 5, `rex.lien_waivers`: 4, `rex.potential_change_orders`: 1, `rex.pending_decisions`: 0.

Prod Rex OS DB has `rex.projects` populated (Phase 4a synced 8 projects) but the financial FK tables are empty because Phase 4 Wave 2 is paused. That means on prod:
- `create_change_event` + `create_decision` work immediately (both need only `project_id`).
- `create_pco` works after the user bootstraps a change event via `create_change_event`.
- `pay_application` + `lien_waiver` are effectively blocked on prod until `rex.commitments` gets populated — but they work fully on demo today, and land immediately when the Phase 4 data strategy ships.

Demo exercises every tool end-to-end. Prod blockers are known and documented.

## Tool set

| slug | class | table | `fires_external_effect` | compensator |
|---|---|---|---|---|
| `create_change_event` | approval, financial | `rex.change_events` | `True` | none |
| `create_pco` | approval, financial | `rex.potential_change_orders` | `True` | none |
| `pay_application` | approval, financial | `rex.payment_applications` | `True` | none |
| `lien_waiver` | approval, financial | `rex.lien_waivers` | `True` | none |
| `create_decision` | auto-pass internal | `rex.pending_decisions` | `False` | DELETE by id |

## Per-tool tool_schema (Anthropic tool_use input_schema)

### `create_change_event`

```jsonc
{
  "description": "Open a new change event on a project. Financial instrument — always requires approval.",
  "input_schema": {
    "type": "object",
    "properties": {
      "project_id": {"type": "string", "description": "UUID of rex.projects."},
      "event_number": {"type": "string", "description": "CE number (text, unique per project)."},
      "title": {"type": "string"},
      "description": {"type": "string"},
      "change_reason": {"type": "string", "enum": ["owner_change","design_change","unforeseen","allowance","contingency"]},
      "event_type": {"type": "string", "enum": ["tbd","allowance","contingency","owner_change","transfer"]},
      "scope": {"type": "string", "enum": ["in_scope","out_of_scope","tbd"]},
      "estimated_amount": {"type": "number", "description": "USD. Defaults to 0."},
      "rfi_id": {"type": "string", "description": "UUID of rex.rfis (optional)."},
      "prime_contract_id": {"type": "string", "description": "UUID of rex.prime_contracts (optional)."}
    },
    "required": ["project_id","event_number","title","change_reason","event_type"]
  }
}
```

Status defaults to `'open'`. `scope` defaults to `'tbd'`. `estimated_amount` defaults to `0`.

### `create_pco`

```jsonc
{
  "description": "Create a Potential Change Order under a change event and commitment. Financial instrument — always requires approval.",
  "input_schema": {
    "type": "object",
    "properties": {
      "change_event_id": {"type": "string"},
      "commitment_id": {"type": "string"},
      "pco_number": {"type": "string"},
      "title": {"type": "string"},
      "amount": {"type": "number"},
      "cost_code_id": {"type": "string"},
      "description": {"type": "string"}
    },
    "required": ["change_event_id","commitment_id","pco_number","title"]
  }
}
```

Status defaults to `'draft'`. `amount` defaults to `0`.

### `pay_application`

```jsonc
{
  "description": "Draft a pay application for a commitment in a given billing period. Financial instrument — always requires approval.",
  "input_schema": {
    "type": "object",
    "properties": {
      "commitment_id": {"type": "string"},
      "billing_period_id": {"type": "string"},
      "pay_app_number": {"type": "integer"},
      "period_start": {"type": "string", "description": "ISO date (YYYY-MM-DD)."},
      "period_end": {"type": "string", "description": "ISO date (YYYY-MM-DD)."},
      "this_period_amount": {"type": "number"},
      "total_completed": {"type": "number"},
      "retention_held": {"type": "number"},
      "retention_released": {"type": "number"},
      "net_payment_due": {"type": "number"}
    },
    "required": ["commitment_id","billing_period_id","pay_app_number","period_start","period_end"]
  }
}
```

Status defaults to `'draft'`. All numeric fields default to `0`.

### `lien_waiver`

```jsonc
{
  "description": "Record a lien waiver under a pay application. Financial instrument — always requires approval.",
  "input_schema": {
    "type": "object",
    "properties": {
      "payment_application_id": {"type": "string"},
      "vendor_id": {"type": "string"},
      "waiver_type": {"type": "string", "enum": ["conditional_progress","unconditional_progress","conditional_final","unconditional_final"]},
      "through_date": {"type": "string", "description": "ISO date."},
      "amount": {"type": "number"},
      "notes": {"type": "string"}
    },
    "required": ["payment_application_id","vendor_id","waiver_type","through_date"]
  }
}
```

Status defaults to `'pending'`. `amount` defaults to `0`.

### `create_decision`

```jsonc
{
  "description": "Flag an open question that needs to be decided on a project. Internal auto-pass; 60s undo.",
  "input_schema": {
    "type": "object",
    "properties": {
      "project_id": {"type": "string"},
      "title": {"type": "string", "description": "The question, as a headline."},
      "description": {"type": "string"},
      "priority": {"type": "string", "enum": ["low","medium","high","critical"]},
      "blocks_description": {"type": "string", "description": "Optional: what downstream work is blocked by this decision."},
      "due_date": {"type": "string", "description": "ISO date (optional)."},
      "decision_maker_id": {"type": "string", "description": "UUID of rex.people — who should make this decision (optional)."}
    },
    "required": ["project_id","title"]
  }
}
```

Status defaults to `'open'`. Priority defaults to `'medium'`. `raised_by` auto-populated by the handler from `ctx.user_account_id` → `rex.people.id` lookup.

## Classifier logic

### Four financial tools (identical shape)

```python
async def _classify(args, ctx):
    amount = args.get("<amount_field>")
    return BlastRadius(
        audience='internal',
        fires_external_effect=True,      # forces approval regardless of amount
        financial_dollar_amount=float(amount) if amount is not None else 0.0,
        scope_size=1,
    )
```

Each tool's `<amount_field>` differs: `estimated_amount` for `create_change_event`, `amount` for `create_pco` and `lien_waiver`, `this_period_amount` (or `net_payment_due`; pick one) for `pay_application`. The dollar amount is informational — it shows up in `BlastRadius.reasons()` for the approval card but doesn't change the approval decision.

### `create_decision`

Identical to Phase 6a `create_note`:

```python
async def _classify(args, ctx):
    return BlastRadius(
        audience='internal',
        fires_external_effect=False,
        financial_dollar_amount=None,
        scope_size=1,
    )
```

`requires_approval()` returns False. Auto-commits with 60s undo.

## Handler shape (summary)

Each handler follows the Phase 6a+Wave 1 pattern:

1. UUID-parse the required FK ids.
2. Handle optional fields (defaults, None-coalesce).
3. `INSERT INTO rex.<table> (...) VALUES (...)` with explicit columns (not `*`).
4. Return `ActionResult(result_payload={<primary_id_field>, <derived_display_fields>})`.

The financial tools raise `ValueError` on missing required FK (e.g., invalid `commitment_id`). The blast-radius classifier runs BEFORE the handler, so classification doesn't depend on the row existing — it only depends on the tool_args the LLM emitted.

## Writeback sequence (§5 spec compliance)

- Phase 6a shipped RFI writeback via `answer_rfi` (2026-04-21).
- 1-month validation window: watch for data drift, webhook reconcile correctness, error rates.
- Next writeback wave: **submittals** (requires Phase 4 Wave 2 data source first, currently blocked).
- After submittals validate: **financial** (adds Procore API writebacks to the 4 Wave 2 tools).

Wave 2 does NOT ship Procore API calls for any of the 5 tools. `rex.change_events` et al. become the source of truth; the old rex-procore writeback stays frozen for these tables (already was — those wrapper tables were empty).

## Compensator

Only `create_decision` has one. Mirrors Phase 6a `create_note`:

```python
async def _compensator(original_result, ctx):
    decision_id = UUID(str(original_result["decision_id"]))
    await ctx.conn.execute(
        "DELETE FROM rex.pending_decisions WHERE id = $1::uuid", decision_id,
    )
    return ActionResult(result_payload={
        "compensated": "create_decision",
        "decision_id": str(decision_id),
    })
```

The 4 financial tools set `compensator=None`. Reversing a committed financial instrument is a semantically different operation (create a void CE, a null PCO, a rejected pay app, a released lien waiver) and belongs to Phase 6c.

## Frontend integration

Zero frontend changes in Wave 2. The Phase 6 frontend Wave 1 `ActionCard` already renders all 4 states (approval, committed, failed, undone) driven by the SSE event stream from `chat_service`. New tools are auto-discovered via the tool registry; the card copy comes from `actionSummary.js`, so Wave 2 adds 5 new cases there.

`actionSummary.js` additions (from plan):
- `create_change_event` → primary "Create change event" + secondary = title
- `create_pco` → primary "Create PCO" + secondary = pco_number + " " + title
- `pay_application` → primary "Draft pay application" + secondary = "Pay app #{pay_app_number}, ${this_period_amount}"
- `lien_waiver` → primary "Record lien waiver" + secondary = "{waiver_type} · ${amount}"
- `create_decision` → primary "Flag decision" + secondary = title

## Testing strategy

Per tool (5 × ~3-4 tests each = ~17 tests):

1. `classify` returns the right BlastRadius (approval-required for financials, auto-pass for create_decision).
2. `handler` INSERTs into the target table with all NOT NULL fields populated correctly from args + defaults.
3. `handler` raises on missing/invalid required FK (e.g., a random UUID for `commitment_id` that doesn't exist).
4. (create_decision only) compensator roundtrip — handler INSERT, compensator DELETE, row is gone.

Cross-cutting:

5. Registry test extension — all 5 new slugs present, `fires_external_effect` matches expected, compensator presence matches expected.
6. Regression — Phase 6a answer_rfi stays `compensator=None`, Phase 6b Wave 1 tools unaffected.

Target: ~17 new tests. Baseline: 957 backend tests currently passing. After Wave 2: ~974 tests passing.

## Deploy + smoke plan

- Railway prod + demo auto-deploy from main after merge.
- Two-pass log check on both Railway envs (established Phase 4/5/6 pattern).
- HTTP surface smoke: `/api/actions/pending` → 401 unauth both envs; `/api/ready` → 200 both envs.
- Demo smoke via a real chat message for at least 2 tools (one financial, one decision) to confirm the SSE → ActionCard → approve/undo loop end-to-end.

## Out of scope for Wave 2

- **Procore writeback** for the 4 financial tools (future financial-writeback wave after submittal writeback lands).
- **`punch_close` / `punch_reopen`** — blocked on `rex.punch_items` data (Phase 4 data strategy).
- **Inspection tools** — no canonical source yet, see `project_phase4_wave2_blocked` memory.
- **`log_meeting_decision`** (insert to `rex.meeting_decisions` requiring meeting_id) — add later if needed.
- **"Send correction" flow** for approval-required tools (Phase 6c).
- **Frontend diff-view or hierarchical CE→PCO→payapp navigation** — separate frontend plan if needed.
- **Schedule tools** — blocked on `rex.schedule_activities` data.
- **Batch/bulk financial tools** — no batch actions in Phase 6.

## Success criteria

- 5 new tools shipped + registered. Tool count goes 9 → 14.
- Backend regression green (957+).
- Demo smoke: chat message triggers `create_change_event` → amber approval card appears with "$XX,XXX.XX" on the reason line → approve → row in `rex.change_events`.
- Demo smoke: chat message triggers `create_decision` → green auto-commit card with 60s countdown → click Undo → row gone from `rex.pending_decisions`.
- Prod smoke: `create_change_event` + `create_decision` work (only need project_id). `create_pco` works after a CE exists. `pay_application` + `lien_waiver` return clear FK-violation errors for now; they'll work once `rex.commitments` is populated.

## Spec self-review

**Placeholder scan:** none. Every tool has a concrete schema, classifier, handler sketch, and target table.

**Internal consistency:** All 4 financial tools share the same classifier shape (only the amount field name differs). All 5 tools follow the `INSERT + return result_payload` pattern from Phase 6a+Wave1. `create_decision` compensator mirrors `create_note` exactly.

**Scope check:** 5 tools + `actionSummary.js` entries + registry.py additions + ~17 tests. Comparable to Wave 1 (5 tools + compensator infra). Shippable in a single PR.

**Ambiguity resolved:** `pay_application`'s `financial_dollar_amount` — which field wins, `this_period_amount` or `net_payment_due`? Locked to `this_period_amount` (what's being billed right now; matches the semantic "the pay app's size this period"). `net_payment_due` is a downstream calculation including retention; less intuitive for approval-card copy.
