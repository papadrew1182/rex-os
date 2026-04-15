"""Drift-detection between ``data/quick_actions_catalog.py`` and the
committed ``migrations/008_ai_action_catalog_seed.sql``.

This test regenerates the migration SQL in memory from the Python source
of truth and compares it byte-for-byte against the checked-in file. If
either one has been edited without the other, the test fails with a
clear diff and points at the regenerate command.

Design notes:
* Pure in-memory regeneration. No file writes during ordinary test runs.
* Imports ``render_migration_sql`` and ``migration_path`` from the build
  script so the test and the generator agree on exactly one rendering.
* Python is the source of truth. If the SQL is out of date, the test
  says "regenerate from Python" — never the other way around.
"""

from __future__ import annotations

import os
import sys

# The build helper lives under ``backend/scripts/`` which is not a package
# on the default sys.path. Insert it explicitly so this test can import
# ``_build_catalog_migration`` the same way the CLI invocation does.
_BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_SCRIPTS_DIR = os.path.join(_BACKEND_DIR, "scripts")
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

from _build_catalog_migration import (  # noqa: E402  (late import, see above)
    MIGRATION_RELATIVE_PATH,
    migration_path,
    render_migration_sql,
)

REGEN_COMMAND = "cd backend && py -3 scripts/_build_catalog_migration.py"


def _read_committed_sql() -> str:
    """Read the committed migration and normalize line endings.

    The generator writes with ``newline="\\n"`` so the canonical form is
    LF. Windows checkouts with ``core.autocrlf=true`` convert to CRLF on
    disk; we undo that here so the test stays green regardless of the
    user's git config.
    """
    with open(migration_path(), "r", encoding="utf-8", newline="") as f:
        raw = f.read()
    return raw.replace("\r\n", "\n")


def test_migration_008_matches_python_source_of_truth():
    """``migrations/008_ai_action_catalog_seed.sql`` must be a byte-for-byte
    image of ``render_migration_sql()`` applied to the current Python
    catalog.

    If this test fails, regenerate the migration with:
        cd backend && py -3 scripts/_build_catalog_migration.py
    then stage ``backend/app/data/quick_actions_catalog.py`` and
    ``migrations/008_ai_action_catalog_seed.sql`` in the same commit.
    """
    expected = render_migration_sql().replace("\r\n", "\n")
    actual = _read_committed_sql()

    if expected == actual:
        return

    expected_lines = expected.splitlines()
    actual_lines = actual.splitlines()

    first_diff = None
    for i, (a, b) in enumerate(zip(expected_lines, actual_lines)):
        if a != b:
            first_diff = (i, a, b)
            break
    if first_diff is None and len(expected_lines) != len(actual_lines):
        first_diff = (
            min(len(expected_lines), len(actual_lines)),
            "<end of shorter file>",
            "<end of shorter file>",
        )

    lineno, exp_line, got_line = first_diff or (0, "", "")
    msg = (
        f"{MIGRATION_RELATIVE_PATH} drifted from "
        f"backend/app/data/quick_actions_catalog.py\n"
        f"  expected line {lineno + 1}: {exp_line!r}\n"
        f"  actual   line {lineno + 1}: {got_line!r}\n"
        f"  expected length: {len(expected)} chars, {len(expected_lines)} lines\n"
        f"  actual   length: {len(actual)} chars, {len(actual_lines)} lines\n"
        f"\nRegenerate with:\n    {REGEN_COMMAND}"
    )
    raise AssertionError(msg)


def test_migration_008_ends_with_trailing_newline():
    """The generator emits a trailing newline; regression-guard it."""
    content = _read_committed_sql()
    assert content.endswith("\n"), (
        f"{MIGRATION_RELATIVE_PATH} must end with a newline. "
        f"Regenerate with: {REGEN_COMMAND}"
    )


def test_render_migration_sql_is_deterministic():
    """Two consecutive renders must be identical — no non-determinism."""
    assert render_migration_sql() == render_migration_sql()
