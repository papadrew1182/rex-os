# Phase 6b Wave 1 — Internal Auto-Pass Tools + Real Undo Compensators

**Status:** approved 2026-04-22 (brainstorm answers locked). Ready for implementation plan.
**Author:** Claude + Andrew Roberts.
**Parent spec:** `docs/superpowers/specs/2026-04-21-phase6-commands-approvals-design.md` (Phase 6 overall).

## Goal

Extend the Phase 6a commands/actions/approvals framework with 5 additional auto-pass internal tools and real undo-compensator logic. Zero Procore writes. After this ships, the assistant can propose and commit 8 total action types, and every auto-committed action can be reversed within 60 seconds with the actual database mutation undone (not just flagged).

**Exit criterion:** Andrew can say "save that email as a draft," get an auto-commit toast, hit "Undo" within 60s, and have the `rex.correspondence` row actually disappear. Same story for the 7 other auto-pass tools across Phase 6a + 6b.

## Pre-locked decisions (from 2026-04-22 brainstorm)

1. **Scope split.** Phase 6b splits into Wave 1 (this spec, internal auto-pass tools + real undo) and Wave 2 (financial tools, Procore writeback, punch transitions, create_decision). Wave 2 waits on submittal writeback validation.
2. **Compensator dispatch.** Undo creates a new action_queue row linked via `correction_of_id`. Undo is auditable as a first-class action, not implicit status flip on the original row.
3. **Delete semantics.** Hard delete. `delete_task` + `delete_note` remove rows; compensators re-insert from a snapshot captured in `result_payload` before the delete.

## Tool set

5 tools, all auto-pass internal (`fires_external_effect=False`, `scope_size=1`, `audience=internal`, `financial=None`).

| slug | table | operation | compensator |
|---|---|---|---|
| `save_meeting_packet` | `rex.meetings` | UPDATE `packet_url` (and optionally `meeting_date`) | UPDATE back to prior `packet_url` |
| `save_draft` | `rex.correspondence` | INSERT with `correspondence_type='email'`, `status='draft'` | DELETE by id |
| `create_alert` | `rex.notifications` | INSERT with user-supplied `severity`, `title`, `notification_type` | DELETE by id |
| `delete_task` | `rex.tasks` | DELETE (after row snapshot) | INSERT from snapshot |
| `delete_note` | `rex.notes` | DELETE (after row snapshot) | INSERT from snapshot |

### Per-tool schemas (Anthropic tool_use)

All schemas follow the Phase 6a pattern: `slug`, human-readable `description`, `input_schema` with required fields clearly marked.

**`save_meeting_packet`** — input: `meeting_id` (uuid, required), `packet_url` (string URL, required), `meeting_date` (ISO date, optional). Only UPDATES the two columns; does not create meetings. If meeting_id doesn't exist, returns failure.

**`save_draft`** — input: `project_id` (uuid, required), `subject` (string, required), `body` (string, required), `to_person_id` (uuid, optional), `from_person_id` (uuid, optional — defaults to current user's person record). Inserts with `correspondence_type='email'`, `status='draft'`. Result_payload carries the inserted id.

**`create_alert`** — input: `user_account_id` (uuid, required — who receives the alert), `notification_type` (string, required — one of an enum passed through directly), `severity` (enum: info/warning/critical, required), `title` (string, required), `body` (string, optional), `project_id` (uuid, optional). Inserts into `rex.notifications`. Result_payload carries the inserted id.

**`delete_task`** — input: `task_id` (uuid, required). Handler snapshots the row to `result_payload['snapshot']` (all columns), then DELETEs. Compensator re-INSERTs from `snapshot`.

**`delete_note`** — input: `note_id` (uuid, required). Same snapshot-then-delete pattern as `delete_task`.

## Compensator infrastructure

### `ActionSpec` extension

Add one optional field to `backend/app/services/ai/tools/base.py`:

```python
CompensatorFn = Callable[[dict, ActionContext], Awaitable[ActionResult]]

@dataclass(frozen=True)
class ActionSpec:
    slug: str
    tool_schema: dict
    classify: ClassifyFn
    handler: HandlerFn
    fires_external_effect: bool = False
    compensator: CompensatorFn | None = None  # NEW
```

If `compensator is None`, the action cannot be undone (`undo()` returns 400). This applies to approval-required tools with external effects (e.g., `answer_rfi`) and any future auto-pass tool that chooses not to implement a compensator.

### Handler contract for undoable tools

Handlers of tools with a compensator MUST populate `result_payload` with everything the compensator needs. Concretely:

- `create_*` handlers: put the created row's `id` (and any other key fields) in result_payload.
- `update_*` handlers: put both the affected `id` AND the prior column values in result_payload (compensator UPDATEs back).
- `delete_*` handlers: put the full row snapshot in result_payload['snapshot'] BEFORE calling DELETE.

### `ActionQueueService.undo()` — new behavior

```python
async def undo(self, action_id: UUID, user_account_id: UUID) -> ActionResult:
    original = await self._repo.get(action_id)
    if original is None:
        raise ActionNotFound(...)
    if original.status != 'auto_committed':
        raise InvalidUndoState(...)
    if (now() - original.committed_at).seconds > self.UNDO_WINDOW_SECONDS:
        raise UndoWindowExpired(...)

    spec = tool_registry.get(original.tool_slug)
    if spec is None or spec.compensator is None:
        raise NotUndoable(...)

    # Insert synthetic correction row
    undo_row_id = await self._repo.insert(
        conversation_id=original.conversation_id,
        message_id=original.message_id,
        user_account_id=user_account_id,
        tool_slug=f"{original.tool_slug}__undo",
        tool_args={},
        blast_radius=original.blast_radius,  # same classification
        requires_approval=False,
        status='auto_committed',
        commit_at=now(),                    # no 60s window on undo itself
        correction_of_id=original.id,
    )

    ctx = ActionContext(user_account_id=user_account_id, original_result=original.result_payload)
    try:
        result = await spec.compensator(original.result_payload, ctx)
    except Exception as e:
        await self._repo.update_status(undo_row_id, status='failed', error_excerpt=str(e)[:500])
        raise CompensatorFailed(...)

    await self._repo.update_status(undo_row_id, status='committed', committed_at=now(), result_payload=result.payload)
    await self._repo.update_status(original.id, status='undone', undone_at=now())
    await self._emit_sse(event='action.undone', payload={'action_id': str(original.id), 'undo_action_id': str(undo_row_id), 'slug': original.tool_slug})
    return result
```

### Why no registry lookup for `__undo` slugs

The suffix `__undo` is a marker. Nothing in the dispatcher processes new tool_use blocks with that slug — those rows are created only by `undo()`. They exist in the queue for audit purposes. `/api/actions/pending` filters them out (WHERE tool_slug NOT LIKE '%\_\_undo' ESCAPE '\\'); they never appear in pending views.

### `ActionContext.original_result`

One new optional field on `ActionContext` (in `base.py`):

```python
@dataclass
class ActionContext:
    user_account_id: UUID
    pool: Any
    # ... existing fields ...
    original_result: dict | None = None  # NEW — populated by undo() for compensator calls
```

Handlers ignore this field (it's only read by compensators).

## Phase 6a retrofit

Phase 6a's 3 auto-pass tools (`create_task`, `update_task_status`, `create_note`) currently have `compensator=None` by default. Wave 1 adds compensators to all three:

- **`create_task._compensator`** — DELETE FROM rex.tasks WHERE id = original_result['task_id']. Requires `task_id` to already be in result_payload (it is — Phase 6a handler returns it).
- **`update_task_status._compensator`** — UPDATE rex.tasks SET status = original_result['prior_status'] WHERE id = original_result['task_id']. Requires Phase 6a handler to capture `prior_status`. **Retrofit needed:** modify the existing `update_task_status.py` handler to read the current status before the UPDATE and put it in result_payload.
- **`create_note._compensator`** — DELETE FROM rex.notes WHERE id = original_result['note_id']. Requires `note_id` in result_payload (it is).

Only `update_task_status` needs a handler-level retrofit. The other two just need compensator functions added.

## SSE events

One new event type: `action.undone` emitted by `undo()` on success. Payload: `{action_id, undo_action_id, slug}`. Frontend eventually renders a "Task was undone" toast; Wave 1 delivers only the backend event.

Existing Phase 6a events unchanged: `action.enqueued`, `action.auto_committed`, `action.pending_approval`, `action.committed`.

## API surface

No new routes. Two behavioral changes to existing routes:

- `POST /api/actions/{action_id}/undo` — now actually reverses the mutation (was Phase 6a no-op). Returns `{status: 'undone', undo_action_id: <uuid>}` on success, 400 on expired window / not undoable, 500 on compensator failure.
- `GET /api/actions/pending` — adds `AND tool_slug NOT LIKE '%\_\_undo'` filter so correction rows don't leak into pending views.

## Testing strategy

**Per new tool** (5 tools × 4 tests):
1. `classify` returns `requires_approval()=False` for representative args.
2. `handler` writes to the correct table + populates `result_payload`.
3. `compensator` reverses the mutation (roundtrip test: handler → compensate → table is back to original state).
4. Registry lookup returns the spec for the tool's slug.

**Cross-cutting** (7 tests):
5. `undo()` on a tool with compensator creates a correction row with `correction_of_id = original.id` and `tool_slug = f"{original.tool_slug}__undo"`.
6. `undo()` outside 60s window returns 400.
7. `undo()` on `answer_rfi` (no compensator) returns 400 "not undoable".
8. `GET /api/actions/pending` does NOT return `__undo` rows.
9. Compensator failure marks correction row `failed`, leaves original `auto_committed`.
10. SSE `action.undone` emitted on successful undo.
11. Phase 6a retrofit: `update_task_status` handler captures `prior_status` into `result_payload`.

Approximately 27 new tests. No regressions on the Phase 6a baseline.

## Out of scope for Wave 1

- **Financial tools** — `pay_application`, `lien_waiver`, `create_change_event`, `create_pco`. Move to Wave 2. These need real thought on Procore writeback ordering (per parent spec §5: submittals first, then these).
- **Punch transitions** — `punch_close`, `punch_reopen`. Wave 2. Status transitions may need to fire notifications to subs; that deserves its own brainstorm pass.
- **`create_decision`** — Wave 2. Needs a new `rex.decisions` table (no existing table matches).
- **Approval-required compensators** ("Send correction" flow for approved `answer_rfi`) — Phase 6c.
- **Frontend card UI + undo toast** — separate frontend plan.
- **Batch detection** — `scope_size>=5` classification still fires, but all 5 Wave 1 tools emit `scope_size=1`. Batch tools are a Wave 2+ concern.

## Success criteria

- All 5 Wave 1 tools shipped + registered.
- All 3 Phase 6a auto-pass tools gain real undo compensators; `update_task_status` handler captures `prior_status`.
- `POST /api/actions/{id}/undo` within 60s actually reverses the DB mutation for all 8 auto-pass tools.
- Full backend test suite green; no Phase 6a regressions.
- Demo + prod deploys clean; `/api/ready` 200; Railway logs show migrations applied without error.

## Spec self-review

**Placeholder scan:** none. Every tool has a concrete table + operation + compensator.

**Internal consistency:** `correction_of_id` reuses the Phase 6a schema column (migration 028 already added it). `ActionContext.original_result` is the one new structural change. Compensator signature matches handler signature structurally so tests can reuse fixtures.

**Scope check:** 5 tools + 3 retrofits + 1 `undo()` rewrite + 1 optional field on `ActionSpec` + 1 optional field on `ActionContext` + 1 SSE event type. Comparable size to Phase 6a's 13 tasks but lower risk (no new external integrations). Shippable in a single PR.

**Ambiguity:** `create_alert.notification_type` currently accepts any string — should it be enum-restricted? Decision: no enum restriction in Wave 1 (rex.notifications.notification_type is already free text, enforcing a list here would duplicate a check that should live at the table level). Flagged for Wave 2 review if misuse shows up.
