"""Optional live Anthropic proof (Session 1).

Marked ``@pytest.mark.live_anthropic``. Skipped automatically when
``ANTHROPIC_API_KEY`` is absent. **Never runs by default** — it is
not part of any merge gate. It makes one small billed streaming call
(max_tokens=50) against the real Anthropic API to prove the
``AnthropicModelClient`` implementation works end-to-end against the
real SDK, not just against the stubbed client used by the hermetic
provider tests.

Run it explicitly with::

    cd backend
    ANTHROPIC_API_KEY=sk-ant-... \\
    REX_RUN_LIVE_ANTHROPIC=1 \\
        py -3 -m pytest tests/test_assistant_live_anthropic_smoke.py \\
                        -v -m live_anthropic

``REX_RUN_LIVE_ANTHROPIC=1`` is a hard opt-in: without it, the test
skips even when the API key is present. This ensures the test
never runs accidentally — e.g. when someone runs ``pytest tests/``
with an API key in their shell profile.

What this proves (live, over the wire):
* ``_try_import_anthropic`` resolves to a real module
* ``AnthropicModelClient._resolve_client`` constructs a real
  ``AsyncAnthropic`` with the configured key
* ``messages.stream(...)`` call signature matches the installed SDK
* ``text_stream`` yields multiple non-empty deltas
* aggregated reply is non-empty

What this does NOT prove:
* chat_service's full SSE vocabulary (covered by the hermetic
  ``test_assistant_anthropic_provider.py`` and by
  ``test_assistant_live_db_smoke.py`` against echo)
* any behavior beyond a single streaming completion
"""

from __future__ import annotations

import os

import pytest

from services.ai.model_client import (
    AnthropicModelClient,
    ModelMessage,
    ModelRequest,
    _try_import_anthropic,
)

pytestmark = pytest.mark.live_anthropic


_HAS_KEY = bool(os.environ.get("ANTHROPIC_API_KEY", "").strip())
_HAS_SDK = _try_import_anthropic() is not None
_OPT_IN = os.environ.get("REX_RUN_LIVE_ANTHROPIC", "").strip().lower() in (
    "1",
    "true",
    "yes",
)

_SKIP_REASON = (
    "Session 1 live-Anthropic proof skipped: requires ANTHROPIC_API_KEY in env, "
    "the `anthropic` Python package installed, AND REX_RUN_LIVE_ANTHROPIC=1. "
    "Run explicitly with `REX_RUN_LIVE_ANTHROPIC=1 pytest -m live_anthropic`. "
    "The hard opt-in prevents accidental billed calls when the key is already "
    "in the shell environment."
)


@pytest.mark.skipif(not (_OPT_IN and _HAS_KEY and _HAS_SDK), reason=_SKIP_REASON)
async def test_live_anthropic_streams_one_small_response():
    """One small, deterministic-shape, real-network streaming call.

    Uses max_tokens=50 so the billed cost is negligible. Asserts the
    streaming path yields at least one non-empty delta and aggregates
    into a non-empty reply. Does not assert the content itself —
    Anthropic output is non-deterministic.
    """
    client = AnthropicModelClient(
        api_key=os.environ["ANTHROPIC_API_KEY"],
    )

    req = ModelRequest(
        model_key=client.model_key,
        system_prompt="Respond in exactly one short sentence. Never more than 20 words.",
        messages=[
            ModelMessage(
                role="user",
                content="Reply with the word 'ok' followed by one short acknowledgement.",
            ),
        ],
        max_tokens=50,
    )

    deltas: list[str] = []
    async for chunk in client.stream_completion(req):
        deltas.append(chunk)

    assert deltas, "live Anthropic call yielded zero deltas"
    non_empty = [d for d in deltas if d.strip()]
    assert non_empty, "live Anthropic call yielded no non-empty deltas"
    full_reply = "".join(deltas)
    assert full_reply.strip(), "live Anthropic reply was whitespace-only"
    print(f"[live_anthropic] model={client.model_key} deltas={len(deltas)} reply={full_reply!r}")
