"""Shared test helpers for all domain test files."""

import uuid

# Seeded deterministic UUIDs from rex2_foundation_bootstrap.sql
PROJECT_BISHOP = "40000000-0000-4000-a000-000000000001"
PROJECT_LAKEWOOD = "40000000-0000-4000-a000-000000000002"
COMPANY_REX = "00000000-0000-4000-a000-000000000001"
COMPANY_EXXIR = "00000000-0000-4000-a000-000000000002"
PERSON_ROBERTS = "10000000-0000-4000-a000-000000000001"
PERSON_MITCH = "10000000-0000-4000-a000-000000000002"
ROLE_VP = "30000000-0000-4000-a000-000000000001"
MEMBER_BISHOP_ROBERTS = "50000000-0000-4000-a000-000000000001"
BOGUS_UUID = "ffffffff-ffff-ffff-ffff-ffffffffffff"


def uid() -> str:
    """Short unique suffix for test data to avoid cross-run collisions."""
    return uuid.uuid4().hex[:8]
