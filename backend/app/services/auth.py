"""Authentication and session management.

Uses the existing rex.user_accounts and rex.sessions tables.
DB-backed sessions chosen over JWT because the sessions table already exists
in the schema and supports explicit revocation via row deletion.
"""

import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID

import bcrypt
from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.foundation import Person, Session, UserAccount

log = logging.getLogger("rex.auth")

SESSION_DURATION_DAYS = 30
# Best-effort: clean up expired sessions at most this often per process.
_EXPIRED_CLEANUP_INTERVAL = timedelta(hours=1)
_last_expired_cleanup: datetime | None = None

# Pre-computed bcrypt hash for unknown-email timing equalization.
# We never reveal or use the plaintext — only the bcrypt call's wall-clock cost matters.
_TIMING_DUMMY_HASH = b"$2b$04$Rx3ioNFONvXvIGXDo3eXWegl4CTL5Vr2XtjF7JgTswRX0FvKcjFWi"


def hash_token(raw_token: str) -> str:
    """SHA-256 hash of a raw bearer token for DB storage."""
    return hashlib.sha256(raw_token.encode()).hexdigest()


def verify_password(password: str, password_hash: str) -> bool:
    """Verify plaintext password against bcrypt hash. Safe against malformed hashes."""
    try:
        return bcrypt.checkpw(password.encode(), password_hash.encode())
    except (ValueError, TypeError):
        return False


async def login(db: AsyncSession, email: str, password: str) -> tuple[UserAccount, str]:
    """Authenticate and create a new session.

    Returns (user, raw_token). The raw token is shown to the client once;
    only its SHA-256 hash is persisted.

    Logs a login-failure event for unknown emails, bad passwords, and
    inactive accounts. The token is **never** logged.
    """
    result = await db.execute(select(UserAccount).where(UserAccount.email == email))
    user = result.scalar_one_or_none()

    # Always run bcrypt to avoid timing oracle on unknown emails
    if user is None:
        bcrypt.checkpw(b"_", _TIMING_DUMMY_HASH)
        log.info("login_failed reason=unknown_email email=%s", email)
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if not verify_password(password, user.password_hash):
        log.info("login_failed reason=bad_password email=%s user_id=%s", email, user.id)
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if not user.is_active:
        log.info("login_failed reason=inactive email=%s user_id=%s", email, user.id)
        raise HTTPException(status_code=401, detail="Account is inactive")

    raw_token = secrets.token_urlsafe(32)
    token_hash = hash_token(raw_token)
    expires_at = datetime.now(timezone.utc) + timedelta(days=SESSION_DURATION_DAYS)

    session_row = Session(
        user_account_id=user.id,
        token_hash=token_hash,
        expires_at=expires_at,
    )
    db.add(session_row)
    user.last_login = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(user)

    log.info("login_ok user_id=%s email=%s", user.id, email)
    return user, raw_token


async def get_user_from_token(db: AsyncSession, raw_token: str) -> UserAccount | None:
    """Resolve a bearer token to a user account, or None if invalid/expired/inactive.

    Also performs an opportunistic cleanup of expired session rows at most once
    per ``_EXPIRED_CLEANUP_INTERVAL``. Cleanup failures are silent — they must
    never block authentication.
    """
    token_hash = hash_token(raw_token)
    now = datetime.now(timezone.utc)

    result = await db.execute(
        select(Session).where(Session.token_hash == token_hash)
    )
    session_row = result.scalar_one_or_none()

    # Opportunistic cleanup of expired sessions (best effort, non-fatal).
    global _last_expired_cleanup
    if (
        _last_expired_cleanup is None
        or now - _last_expired_cleanup > _EXPIRED_CLEANUP_INTERVAL
    ):
        _last_expired_cleanup = now
        try:
            await db.execute(delete(Session).where(Session.expires_at < now))
            await db.commit()
        except Exception:
            await db.rollback()

    if session_row is None:
        return None
    if session_row.expires_at < now:
        return None
    user = await db.get(UserAccount, session_row.user_account_id)
    if user is None or not user.is_active:
        return None
    return user


async def logout(db: AsyncSession, raw_token: str) -> bool:
    """Delete the session row for a token. Returns True if a row was removed."""
    token_hash = hash_token(raw_token)
    result = await db.execute(
        select(Session).where(Session.token_hash == token_hash)
    )
    session_row = result.scalar_one_or_none()
    if session_row is None:
        return False
    user_id = session_row.user_account_id
    await db.delete(session_row)
    await db.commit()
    log.info("logout_ok user_id=%s", user_id)
    return True


async def logout_all_sessions(db: AsyncSession, user_id: UUID) -> int:
    """Revoke every session row belonging to ``user_id``. Returns row count.

    Scoped to the caller's own account at the route layer — this helper
    itself takes the id explicitly so there is no ambient-authority path.
    """
    result = await db.execute(
        delete(Session).where(Session.user_account_id == user_id)
    )
    await db.commit()
    count = result.rowcount or 0
    log.info("logout_all user_id=%s revoked=%d", user_id, count)
    return count


async def purge_expired_sessions(db: AsyncSession) -> int:
    """Delete every session row whose expires_at is in the past.

    Deterministic counterpart to the opportunistic cleanup inside
    ``get_user_from_token``. Safe to call from tests or a future scheduled
    job. Returns the number of rows removed.
    """
    now = datetime.now(timezone.utc)
    result = await db.execute(delete(Session).where(Session.expires_at < now))
    await db.commit()
    count = result.rowcount or 0
    if count:
        log.info("purge_expired_sessions removed=%d", count)
    return count


async def get_person_for_user(db: AsyncSession, user: UserAccount) -> Person | None:
    """Load the linked Person row for a user account, if any."""
    if user.person_id is None:
        return None
    return await db.get(Person, user.person_id)
