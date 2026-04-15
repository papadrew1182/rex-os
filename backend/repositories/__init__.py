"""Repositories package (Session 1 — feat/ai-spine).

Thin asyncpg-backed data access for the AI spine. Repositories here are
allowed to read any ``rex.*`` table/view that the charter owns for this
lane, but must NOT read connector schemas directly — that is Session 2's
job and is enforced in the SQL guard.
"""
