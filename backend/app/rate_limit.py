"""Shared slowapi limiter instance.

Lives in its own module so routers (``app.routes.auth``) can import the
limiter without pulling in ``main`` — otherwise we'd have a circular import
at startup.

Rate limit strings use slowapi syntax (e.g. ``10/minute``). The login
default is intentionally generous so a legitimate mistyped password burst
doesn't lock a user out; it only blocks obvious brute-force volume.

Wiring (done in ``main.py``):
    from app.rate_limit import limiter
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

Usage (done on individual routes):
    from app.rate_limit import limiter, LOGIN_RATE_LIMIT
    @router.post("/login")
    @limiter.limit(LOGIN_RATE_LIMIT)
    async def login(request: Request, ...): ...
"""

from __future__ import annotations

import os

from slowapi import Limiter
from slowapi.util import get_remote_address

# Login rate limit — override with REX_LOGIN_RATE_LIMIT in prod.
# 10/minute per client IP: legitimate users won't hit it; brute force will.
LOGIN_RATE_LIMIT: str = os.getenv("REX_LOGIN_RATE_LIMIT", "10/minute")

limiter = Limiter(key_func=get_remote_address, default_limits=[])
