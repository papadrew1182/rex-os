# Phase 6 — Commands, Actions & Approvals Design

**Status:** approved 2026-04-21 (brainstorm answers pre-locked + §3 clarification), ready for implementation plan.
**Author:** Claude + Andrew Roberts.

## Goal

Turn natural-language assistant messages into safe structured actions that mutate Rex OS state and (when appropriate) Procore. Every action is classified at runtime along four blast-radius dimensions; low-impact actions auto-commit with a 60-second undo, higher-impact ones enter an approval queue. Rex OS becomes the source of truth for Procore objects; the legacy rex-procore writeback module freezes.

**Exit criterion:** Andrew can type "draft a response to RFI-42 saying the duct conflict is resolved" and (a) see a confirmation card with real downstream effects, (b) approve it once, (c) have the RFI update land in Rex OS + the Procore mutation fire in-band, with a clean undo/correction path if he changes his mind.

## Pre-locked decisions (from memory)

See `memory/project_phase6_design_decisions.md` for the full brainstorm record. Seven of eight sections answered there; §3 got one additional clarification in this spec.

| # | Section | Answer |
|---|---|---|
| 1 | Parse strategy | Anthropic tool use with schema-validated arguments |
| 2 | Confirmation card | Summary + target link + downstream effects + quoted trigger; diff (collapsed) for edits; mobile full-screen with sticky approve/discard |
| 3 | Blast-radius rubric | 4 dimensions (audience, reversibility, financial, scope); category is hint, blast radius is the rule. Clarified below |
| 4 | Approver routing | Per-role queue; VP global view; Andrew self-approves via card; no countersign to start; delegate = downstream owner |
| 5 | Writeback | Direct Rex OS → Procore. Freeze rex-procore writeback. RFIs first, submittals next, rest follows |
| 6 | Undo window | 60s for auto-pass only; external-side-effect actions become "Send correction" not undo |
| 7 | Failure semantics | Stop on first failure; no cross-system rollback; per-row UI state; "Retry failed + pending" button |
| 8 | Conversation state | Both views, conversation primary; "Pending Approvals" is a filter, not the main surface |

## §3 clarification — what's "irreversible"

**A (picked).** Reversibility is about whether the action's handler itself fires an external side effect. A `rex.rfis` UPDATE is reversible (60s undo can roll it back before the next Procore webhook tick). A direct Procore API call is irreversible. Implementation: each action opts into irreversible classification via a `fires_external_effect=True` flag in its definition, grep-able.

## Architecture

### Four layers

1. **Tool registry** (`backend/app/services/ai/tools/`) — one module per action. Each module exports:
   - `slug: str`
   - `tool_schema: dict` — Anthropic tool use JSON schema the model sees
   - `handler(args, ctx) -> ActionResult` — executes the action
   - `classify(args, ctx) -> BlastRadius` — pure function, no I/O
   - `fires_external_effect: bool` — set True for handlers that call Procore API / SMTP / etc.
2. **Blast-radius classifier** (`backend/app/services/ai/actions/blast_radius.py`) — dataclass + `requires_approval()` boolean. Consumes `BlastRadius` objects from tool.classify.
3. **Action queue** (new `rex.action_queue` table) — rows for `pending_approval`, `auto_committed`, `pending_retry`, `committed`, `failed`, `undone`. Powers both the conversation inline cards and the filtered "Pending Approvals" view.
4. **Execution dispatcher** — chat_service already has a hook for `active_action_slug` (Phase 5). Extend to intercept LLM tool_use responses, classify via the rubric, either commit (auto) or enqueue (approval). Tool_use vs slug-dispatch: slug stays for quick actions; tool_use is the new path for LLM-generated actions. Both flow through the same queue.

### Data flow for one LLM action

```
user → chat → LLM tool_use response
      ↓
  tool_registry.get(tool_name) → ActionSpec
      ↓
  classify(args, ctx) → BlastRadius
      ↓
  requires_approval()?
      ├─ no  → insert into action_queue status='auto_committed' with commit_at = now()+60s
      │       → schedule commit after 60s (background task) OR commit immediately if user hits "undo" window expires
      │       → user can hit "undo" within 60s → status='undone'
      │
      └─ yes → insert into action_queue status='pending_approval'
              → render confirmation card inline in the chat stream
              → user approves via card → status='committed', handler fires
              → user discards → status='dismissed'
```

### Schema additions

Migration adds `rex.action_queue`:

```sql
CREATE TABLE rex.action_queue (
    id             uuid PK DEFAULT gen_random_uuid(),
    conversation_id uuid REFERENCES rex.chat_conversations(id),
    message_id     uuid REFERENCES rex.chat_messages(id),  -- the user turn that triggered it
    user_account_id uuid NOT NULL REFERENCES rex.user_accounts(id),  -- who the action runs AS
    requested_by_user_id uuid REFERENCES rex.user_accounts(id),       -- who triggered (may differ for delegate scenarios)
    tool_slug      text NOT NULL,
    tool_args      jsonb NOT NULL,
    blast_radius   jsonb NOT NULL,  -- serialized BlastRadius dataclass
    requires_approval boolean NOT NULL,
    status         text NOT NULL CHECK IN ('auto_committed','pending_approval','committed','dismissed','undone','failed','pending_retry'),
    commit_at      timestamptz,      -- for auto_committed: t + 60s undo window
    committed_at   timestamptz,
    undone_at      timestamptz,
    error_excerpt  text,
    result_payload jsonb,             -- handler return value on commit; used for correction UI
    correction_of_id uuid REFERENCES rex.action_queue(id),  -- if this action is a "send correction" compensator
    created_at     timestamptz NOT NULL DEFAULT now(),
    updated_at     timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_action_queue_status ON rex.action_queue (status);
CREATE INDEX idx_action_queue_user_pending ON rex.action_queue (user_account_id, status) WHERE status = 'pending_approval';
CREATE INDEX idx_action_queue_conversation ON rex.action_queue (conversation_id);
```

## Blast-radius classifier

```python
# backend/app/services/ai/actions/blast_radius.py
@dataclass(frozen=True)
class BlastRadius:
    audience: Literal['internal', 'external']
    fires_external_effect: bool
    financial_dollar_amount: float | None
    scope_size: int

    def requires_approval(self) -> bool:
        return (
            self.audience == 'external'
            or self.fires_external_effect
            or (self.financial_dollar_amount is not None and self.financial_dollar_amount > 0)
            or self.scope_size >= 5
        )

    def reasons(self) -> list[str]:
        """Human-readable reasons for the confirmation card's
        'why this needs approval' footnote."""
        r = []
        if self.audience == 'external':
            r.append("will notify someone outside Rex Construction")
        if self.fires_external_effect:
            r.append("writes to an external system (Procore)")
        if self.financial_dollar_amount and self.financial_dollar_amount > 0:
            r.append(f"financial impact: ${self.financial_dollar_amount:,.2f}")
        if self.scope_size >= 5:
            r.append(f"batch of {self.scope_size} changes")
        return r
```

Each tool's `classify(args, ctx)` returns a `BlastRadius`. Context includes the current user, the tool's schema, and a helper:

```python
class ClassifyContext:
    user_account_id: UUID
    async def is_internal_person(self, person_id: UUID) -> bool: ...  # rex.people.role_type == 'internal'
    async def is_external_email(self, email: str) -> bool: ...  # not a Rex domain
```

## MVP action set (ship in the first Phase 6 PR)

Start small to prove the framework. 3 auto-pass + 1 approval-required = 4 tools.

1. **`create_task`** — inserts into `rex.tasks`. Auto if assignee is the requester or another internal Rex person. Approval if assignee is external (including company_members/subs). `fires_external_effect=False`. `scope_size=1`.
2. **`update_task_status`** — updates `rex.tasks.status`. Auto always (internal data mutation, single row, no Procore push). `fires_external_effect=False`.
3. **`create_note`** — inserts into `rex.notes` (or similar internal scratchpad — check schema for actual table; may need a new one). Auto always.
4. **`answer_rfi`** — updates `rex.rfis.answer` + `status='answered'` + fires Procore API call. Always approval-required (fires_external_effect=True). This is the canonical "approval queue works end to end" test.

Deferred to Phase 6b (follow-up plan):
- save_meeting_packet, save_draft, create_alert, create_decision (all auto-pass, more of the same as #1-3)
- CE/PCO creation, pay-app actions, punch close/reopen (all approval-required)
- Delete operations across the board

## Confirmation card UX (simplest defensible version)

Rendered inline in the chat stream as a structured SSE event the frontend interprets. Card shape:

```
┌─────────────────────────────────────────────────┐
│ ⚠ Approval required                             │
│                                                 │
│ Answer RFI-42 "Duct conflict at grid B/4"       │
│ with: "Confirmed — use revised detail A-501"   │
│                                                 │
│ Will notify GC and close the RFI in Procore.   │
│                                                 │
│ ▾ Triggered by: "mark RFI-42 as answered, the   │
│    duct conflict is resolved"                   │
│                                                 │
│      [ Discard ]            [ Approve ]         │
└─────────────────────────────────────────────────┘
```

For creates (no diff): the card body IS the payload.
For edits: collapsed "Show changes" toggle reveals the diff; 3 most-recent field changes shown, remainder hidden.
Mobile: full-screen modal below the fold; buttons stick to bottom.
Approval-required cards show an "ℹ why" line listing `BlastRadius.reasons()`.

## Undo + correction

**Auto-pass actions** get a 60s undo. Implementation:
- Handler fires immediately on commit (no real delay for the user's perception).
- Background job scoped by `commit_at > now()` can roll back via the inverse of the handler (e.g., `update_task_status`'s undo is an `update_task_status` back to the prior value).
- If the user hits "Undo" in the UI within 60s, we dispatch a compensator action OF THE SAME BLAST-RADIUS CLASS (so an internal-only action's undo is also internal-only, a Procore-writing action's undo is ALSO an external call — which is why those don't get real undo).

**Approval-required actions** don't have undo. Once approved + committed, the user can trigger a "Send correction" which is a new action that CAN have its own approval flow. UI copy distinguishes "Undo" (reversible) from "Send correction" (compensating; another external effect) so the user knows what they're getting.

## Failure semantics

Per decision #7:
- Batch commit stops on first failure. Committed rows stay committed.
- Failed row: status='failed', error_excerpt populated, UI shows the real underlying asyncpg/httpx message. Red row.
- Pending rows: status='pending_retry', UI shows gray + "Skipped — retry?". One "Retry failed + pending" button re-dispatches both.
- No timeout — failed rows persist until manually dismissed or successfully retried.

Cross-system rollback is NOT a thing. If an action's handler writes to Rex OS then fails the Procore call, the Rex OS write stays; the Procore reconcile webhook will eventually correct it. Documented explicitly.

## Writeback (§5) — rex-procore freeze sequence

1. Phase 6a lands `answer_rfi` with direct Procore API call (bypasses rex-procore writeback).
2. Validate for one month that no data drift appears (Procore objects and rex.rfis stay consistent via webhooks + explicit writeback).
3. Phase 6b adds submittals + ports the remaining rex-procore writeback calls.
4. Phase 6c freezes rex-procore writeback (read-only) and removes the module from the old app's cron.

Explicit NOT in scope: async dual-write. Decision #5 was clear — direct, with webhook reconcile.

## Approver routing (§4 — simplest version)

- Every pending_approval row has an `approver_role` column derived from the tool's declared permission (e.g., `answer_rfi.required_permission = 'write:rfis'` → approver_role = 'pm' | 'vp').
- `/api/actions/pending?role=vp` returns the VP's global queue.
- `/api/actions/pending` (no filter) returns the requesting user's own queue.
- Andrew, being a VP, sees both.
- No countersign flag in MVP. Add later when a real incident suggests where it's needed.

## Conversation state (§8)

- Approval cards live inline in the chat conversation thread (rendered when the frontend sees an `action_card` SSE event).
- "Pending Approvals" sidebar view is a filter query over `rex.action_queue WHERE status='pending_approval' AND (user_account_id = me OR approver_role IN my_roles)`. Clicking jumps to the card's conversation.
- Do NOT build a separate "inbox" UI. Cards are conversation primary; the filter is just a convenience.

## API surface

New endpoints:

- `POST /api/actions/{action_id}/approve` — marks status=committed, fires handler, returns result.
- `POST /api/actions/{action_id}/discard` — marks status=dismissed.
- `POST /api/actions/{action_id}/undo` — for auto_committed actions within 60s; dispatches compensator.
- `GET  /api/actions/pending?role=<role>` — queue view, per #8.

Existing `/api/assistant/chat` SSE stream gains new event types:
- `event: action_proposed` — when LLM emits a tool_use; frontend renders the card.
- `event: action_auto_committed` — when an action skipped the approval queue; frontend shows a "Undoable for 60s" toast.
- `event: action_committed` — after approval + handler success.
- `event: action_failed` — with error_excerpt.

## Testing strategy

- **Unit tests per tool** (4 handlers × 3-5 tests each): `classify` returns correct BlastRadius for representative arg combinations; `handler` persists correctly when called directly.
- **Dispatcher integration tests**: LLM tool_use → classify → enqueue → approve → handler. Mocked model_client returns a canned tool_use response.
- **End-to-end approval-required**: POST chat with "mark RFI-42 as answered", assert action_queue has a pending_approval row; POST /api/actions/{id}/approve, assert rex.rfis updated + Procore mock API was called.
- **End-to-end auto-pass with undo**: POST chat with "create a task to check the punch list", assert auto_committed row + rex.tasks row + commit_at = now+60s. POST /api/actions/{id}/undo within 60s, assert rex.tasks row deleted, status='undone'.
- **Failure test**: tool handler raises; assert status='failed' with error_excerpt.
- **Blast-radius unit tests**: each of the 4 dimensions exercised individually + combined (e.g., external + financial → definitely approval; external + internal-looking-dollar-of-zero → still approval because external wins).

## Out of scope for Phase 6 MVP (follow-up plans)

- **Phase 6b** — remaining ~12 actions (save_meeting_packet, save_draft, create_alert, create_decision, pay-app, lien waiver, CE, PCO, punch close/reopen, delete variants).
- **Phase 6c** — full rex-procore writeback freeze + removal.
- **Frontend card UI** — this spec covers the backend-side event contract. The React card component is a separate frontend plan (`2026-04-XX-phase6-card-ui.md`). Backend ships first; frontend can consume via the existing SSE handler.
- **Countersign rules** — revisit after 2 weeks of real usage.
- **Delegate-queue UX** — if AI acts on behalf of someone else, approver routing is mechanical (downstream owner gets the card). UI affordances for "the AI proposed this on behalf of X" are a Phase 6b polish item.

## Success criteria

- Andrew runs through "create a task for me" and sees a 60s undo toast.
- Andrew runs through "answer RFI-42 with ..." and sees a real confirmation card with the downstream effects listed; approval commits both the rex.rfis update AND the Procore API call.
- Failure injection (Procore API 500 response) leaves rex.rfis updated + action_queue.status='failed' with a human-readable error_excerpt.
- Full test suite stays green; no regressions on the existing 875 tests.

## Spec self-review

**Placeholder scan:** None. Every section has a concrete mechanism.
**Consistency:** The 4 blast-radius dimensions are referenced consistently (classifier class, card reason strings, schema serialization as jsonb). "fires_external_effect" opt-in is mentioned in §3 clarification + tool definition + blast-radius dataclass.
**Scope check:** MVP scope is 4 tools + the framework. Approval-required/undo/failure paths all exercised by the single `answer_rfi` tool. Shippable without being trivial.
**Ambiguity:** One remaining: the `rex.notes` table for `create_note` may not exist — the implementer will need to either add a new table via migration OR pick an existing alternative (pending_decisions? visit notes on daily_logs?). Flagged in the implementation plan's discovery step.
