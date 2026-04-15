"""One-shot build helper: regenerate ``migrations/008_ai_action_catalog_seed.sql``
from ``backend/data/quick_actions_catalog.py``.

Run from ``backend/`` with::

    py -3 scripts/_build_catalog_migration.py

Lives in ``scripts/`` (not ``services/``) because it is a build-time tool,
not an application runtime module.
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from data.quick_actions_catalog import (  # noqa: E402
    CANONICAL_SLUG_COUNT,
    LEGACY_ALIAS_COUNT,
    QUICK_ACTIONS_CATALOG,
)
from services.ai.catalog_import import validate_catalog  # noqa: E402


HEADER = """-- Migration 008: AI spine — full quick-action catalog seed
--
-- Session 1 (feat/ai-spine) Work Packet C.
--
-- Forward-only idempotent bootstrap of the canonical {slug_count}-slug /
-- {alias_count}-alias quick-action catalog. The source of truth is the
-- Python list at ``backend/data/quick_actions_catalog.py``. Both files
-- must stay in sync. This file is REGENERATED from the Python source via
-- ``py -3 scripts/_build_catalog_migration.py`` (run from backend/).
-- Do not hand-edit the JSONB blob below.
--
-- Dedupes encoded:
--   C-5  + C-29 -> rfi_aging              (Session 3 mockCatalog parity)
--   C-8  + C-28 -> submittal_sla          (charter-required)
--   C-15 + C-60 -> monthly_owner_report   (charter-required)
--
-- Harmonization vs migration 007:
--   * daily_log_summary   category: FIELD_OPS  -> PROJECT_MGMT
--   * monthly_owner_report category: REPORTING -> EXECUTIVE
--   * morning_briefing    category: MYDAY      -> OPERATIONS
--   * scorecard_preview   category: PORTFOLIO  -> PERFORMANCE
--   * slug rename: lookahead_2week -> two_week_lookahead
--
-- Row-level idempotency: ON CONFLICT (slug) DO UPDATE SET <all fields>.
-- Running this migration on a DB that already has the full catalog is a
-- safe no-op because every field is set from EXCLUDED.

-- Step 1: rename the one pre-existing slug that was harmonized against
-- the mockCatalog and the rex-procore panels.
UPDATE rex.ai_action_catalog
   SET slug = 'two_week_lookahead'
 WHERE slug = 'lookahead_2week';

-- Step 2: bulk upsert from an inline JSONB payload. jsonb_to_recordset
-- unpacks the array into typed columns; text[] fields are materialized
-- via jsonb_array_elements_text inside the SELECT.
WITH seed AS (
    SELECT *
    FROM jsonb_to_recordset($CATALOG_SEED$
"""

FOOTER = """
$CATALOG_SEED$::jsonb) AS t(
        slug text,
        legacy_aliases jsonb,
        label text,
        category text,
        description text,
        params_schema jsonb,
        risk_tier text,
        readiness_state text,
        required_connectors jsonb,
        role_visibility jsonb,
        handler_key text,
        enabled boolean,
        metadata jsonb
    )
)
INSERT INTO rex.ai_action_catalog
    (slug, legacy_aliases, label, category, description,
     params_schema, risk_tier, readiness_state,
     required_connectors, role_visibility, handler_key,
     enabled, metadata)
SELECT
    slug,
    ARRAY(SELECT jsonb_array_elements_text(legacy_aliases)),
    label,
    category,
    description,
    params_schema,
    risk_tier,
    readiness_state,
    ARRAY(SELECT jsonb_array_elements_text(required_connectors)),
    ARRAY(SELECT jsonb_array_elements_text(role_visibility)),
    handler_key,
    enabled,
    metadata
FROM seed
ON CONFLICT (slug) DO UPDATE SET
    legacy_aliases      = EXCLUDED.legacy_aliases,
    label               = EXCLUDED.label,
    category            = EXCLUDED.category,
    description         = EXCLUDED.description,
    params_schema       = EXCLUDED.params_schema,
    risk_tier           = EXCLUDED.risk_tier,
    readiness_state     = EXCLUDED.readiness_state,
    required_connectors = EXCLUDED.required_connectors,
    role_visibility     = EXCLUDED.role_visibility,
    handler_key         = EXCLUDED.handler_key,
    enabled             = EXCLUDED.enabled,
    metadata            = EXCLUDED.metadata;
"""


def main() -> int:
    validate_catalog()  # blow up if the source has drifted
    blob = json.dumps(QUICK_ACTIONS_CATALOG, indent=2)
    content = (
        HEADER.format(slug_count=CANONICAL_SLUG_COUNT, alias_count=LEGACY_ALIAS_COUNT)
        + blob
        + FOOTER
    )

    target = os.path.abspath(
        os.path.join(
            os.path.dirname(__file__),
            "..",
            "..",
            "migrations",
            "008_ai_action_catalog_seed.sql",
        )
    )
    with open(target, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)
    print(f"wrote {target} ({len(content)} chars)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
