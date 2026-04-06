# Rex OS

Construction management platform — clean-slate successor to Rex 2.0.

## Stack

- **Backend:** Python 3.12 + FastAPI + asyncpg
- **Frontend:** React 18 + Vite
- **Database:** PostgreSQL — `rex.*` schema
- **Deploy:** Railway

## Local Setup

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

### Database

```bash
psql -U postgres -c "CREATE DATABASE rex_os;"
psql -U postgres -d rex_os -f migrations/001_create_schema.sql
```

## Conventions

- Schema: `rex.*` — all core tables live here
- Primary keys: `uuid` with `gen_random_uuid()` default
- Foreign keys: `{table_singular}_id`
- Timestamps: `timestamptz`, every table gets `created_at`; mutable tables get `updated_at`
- Booleans: `is_` or `has_` prefix
- Enums: `text` type, validated in application layer
- External IDs: zero Procore columns on core tables — all mapping via `rex.connector_mappings`
- SQL params: asyncpg `$1`/`$2` style

## Project Structure

```
rex-os/
  backend/          FastAPI app
    main.py         Entry point, routes
    db.py           asyncpg pool
    routers/        Feature routers
    models/         Pydantic models
  frontend/         React + Vite SPA
    src/
    dist/           Compiled output (committed, Railway serves this)
  migrations/       Sequential SQL migrations
  docs/             Architecture and design docs
```

## Running Migrations

```
GET /api/admin/migrate?secret={MIGRATE_SECRET}
```
