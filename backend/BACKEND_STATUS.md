# Rex OS Backend — Status

## Current state: CRUD baseline complete

All 6 domains are implemented with consistent async SQLAlchemy + FastAPI CRUD:

| Domain | Tables | Routers | Endpoints | Tests |
|--------|--------|---------|-----------|-------|
| Foundation | 9 | 6 | 24 | 26 |
| Schedule | 5 | 5 | 19 | 31 |
| Field Ops | 12 | 12 | 48 | 32 |
| Financials | 14 | 14 | 52 | 35 |
| Document Management | 9 | 9 | 34 | 27 |
| Closeout & Warranty | 8 | 8 | 32 | 26 |
| **Total** | **57** | **54** | **209** | **177+** |

## Architecture

- **ORM**: SQLAlchemy 2.0 async mapped columns, one model file per domain
- **Schemas**: Pydantic v2 with Literal validation on enum-ish fields
- **Services**: Per-domain service modules with filtered list queries + shared CRUD helpers
- **Routes**: Thin FastAPI routers delegating to service layer
- **Errors**: SQLSTATE-based classification (409 unique, 422 FK/check, 404 not found)
- **Tests**: pytest-asyncio with session-scoped ASGI client against real DB

## Next phase: workflow / business logic

The CRUD baseline is intentionally behavior-free. The next implementation targets are:

1. **Closeout checklist from template** — copy template items into a project checklist
2. **Checklist percent_complete rollup** — auto-compute from child item statuses
3. **Warranty expiration helper** — compute expiration_date from start_date + duration_months on create
4. **Warranty alert generation** — auto-create 90-day, 30-day, expired alerts on warranty create
5. **Milestone evidence helper** — track evidence checklist completion against JSONB requirements
6. **Holdback release gate conditions** — evaluate punch aging, warranty defects, closeout status
7. **Budget rollup math** — auto-compute revised_budget, projected_cost, over_under from components
8. **RFI/submittal aging** — compute days_open on read

These should be implemented as service-layer functions called by existing routes,
not as new endpoints unless clearly needed.
