"""Chat service — produces the SSE event stream for POST /api/assistant/chat.

SSE event vocabulary (frozen for Session 3):

    conversation.created
    message.started
    message.delta
    message.completed
    followups.generated
    action.suggestions
    error

Each event is a single JSON object serialized on its own ``data:`` line,
terminated by a blank line. The event type lives in the payload itself.
"""

from __future__ import annotations

import json
import logging
from typing import Any, AsyncIterator

import asyncpg

from app.repositories.chat_repository import ChatRepository
from app.schemas.assistant import AssistantChatRequest, AssistantUser
from app.services.ai.action_dispatcher import ActionDispatcher, _default_dispatcher
from app.services.ai.actions.base import ActionContext
from app.services.ai.context_builder import AssistantContext
from app.services.ai.followups import FollowupGenerator
from app.services.ai.model_client import (
    ModelClient,
    ModelMessage,
    ModelRequest,
    ProviderNotConfigured,
)

log = logging.getLogger(__name__)


def sse_event(payload: dict[str, Any]) -> str:
    return f"data: {json.dumps(payload, default=str)}\n\n"


class ChatService:
    def __init__(
        self,
        *,
        chat_repo: ChatRepository,
        model_client: ModelClient,
        followup_generator: FollowupGenerator,
        pool: asyncpg.Pool | None = None,
        action_dispatcher: ActionDispatcher | None = None,
    ) -> None:
        self._chat_repo = chat_repo
        self._model = model_client
        self._followups = followup_generator
        self._pool = pool
        self._action_dispatcher = action_dispatcher or _default_dispatcher

    async def stream_chat(
        self,
        *,
        request: AssistantChatRequest,
        user: AssistantUser,
        context: AssistantContext,
    ) -> AsyncIterator[str]:
        conversation = await self._resolve_conversation(request=request, user=user)
        created_now = request.conversation_id is None
        if created_now:
            yield sse_event(
                {"type": "conversation.created", "conversation_id": str(conversation["id"])}
            )

        try:
            user_msg = await self._chat_repo.append_message(
                conversation_id=conversation["id"],
                sender_type="user",
                content=request.message,
                structured_payload={
                    "params": request.params,
                    "active_action_slug": request.active_action_slug,
                    "mode": request.mode,
                },
            )
        except Exception as exc:  # noqa: BLE001
            log.exception("failed to persist user message")
            yield sse_event(
                {
                    "type": "error",
                    "code": "persist_user_message_failed",
                    "message": str(exc),
                }
            )
            return

        yield sse_event(
            {
                "type": "message.started",
                "conversation_id": str(conversation["id"]),
                "user_message_id": str(user_msg["id"]),
            }
        )

        history = await self._chat_repo.list_messages(conversation["id"])

        # Quick-action prompt injection. If the request carries an
        # ``active_action_slug`` matching a registered handler, run it and
        # append its ``prompt_fragment`` to the system prompt before the
        # model call. Missing pool or unknown slug is a no-op.
        action_fragment = ""
        if request.active_action_slug and self._pool is not None:
            async with self._pool.acquire() as _conn:
                action_ctx = ActionContext(
                    conn=_conn,
                    user_account_id=user.id,
                    project_id=getattr(context, "project_id", None),
                    params=dict(request.params or {}),
                )
                action_result = await self._action_dispatcher.maybe_execute(
                    request.active_action_slug, action_ctx,
                )
            if action_result is not None:
                action_fragment = "\n\n" + action_result.prompt_fragment

        effective_system_prompt = context.system_prompt + action_fragment

        model_request = ModelRequest(
            model_key=getattr(self._model, "model_key", "echo"),
            system_prompt=effective_system_prompt,
            messages=[
                ModelMessage(role="system", content=effective_system_prompt),
                *[
                    ModelMessage(role=_sender_to_role(m["sender_type"]), content=m["content"])
                    for m in history
                    if m["sender_type"] in {"user", "assistant"}
                ],
            ],
        )

        delta_buffer: list[str] = []
        try:
            async for delta in self._model.stream_completion(model_request):
                delta_buffer.append(delta)
                yield sse_event({"type": "message.delta", "delta": delta})
        except ProviderNotConfigured as exc:
            # Deterministic, actionable error surface for misconfigured
            # providers. ``exc.code`` is one of the stable codes defined
            # on ``ProviderNotConfigured`` (e.g. ``anthropic_sdk_missing``,
            # ``anthropic_api_key_missing``). The chat stream terminates
            # here without persisting an assistant message.
            yield sse_event(
                {
                    "type": "error",
                    "code": exc.code,
                    "message": exc.message,
                }
            )
            return
        except Exception as exc:  # noqa: BLE001
            log.exception("model stream failed")
            yield sse_event(
                {
                    "type": "error",
                    "code": "model_stream_failed",
                    "message": str(exc),
                }
            )
            return

        full_reply = "".join(delta_buffer)

        followups = self._followups.suggest(
            active_action_slug=request.active_action_slug,
            last_user_message=request.message,
        )
        followup_labels = [f.label for f in followups]
        yield sse_event({"type": "followups.generated", "items": followup_labels})

        assistant_msg = await self._chat_repo.append_message(
            conversation_id=conversation["id"],
            sender_type="assistant",
            content=full_reply,
            structured_payload={"followups": followup_labels},
            model_key=getattr(self._model, "model_key", "echo"),
            prompt_key="assistant.system.base",
        )

        await self._chat_repo.touch_conversation(
            conversation["id"],
            title=_derive_title_if_needed(conversation, request.message),
            active_action_slug=request.active_action_slug,
        )

        yield sse_event(
            {
                "type": "message.completed",
                "conversation_id": str(conversation["id"]),
                "message_id": str(assistant_msg["id"]),
            }
        )

    async def _resolve_conversation(
        self, *, request: AssistantChatRequest, user: AssistantUser
    ) -> dict[str, Any]:
        if request.conversation_id is not None:
            existing = await self._chat_repo.get_conversation(
                request.conversation_id, user_id=user.id
            )
            if existing is not None:
                return existing
        return await self._chat_repo.create_conversation(
            user_id=user.id,
            title=_title_seed_from_message(request.message),
            project_id=request.project_id,
            active_action_slug=request.active_action_slug,
            page_context=request.page_context.model_dump(),
            conversation_metadata={"origin": "assistant_sidebar"},
        )


def _sender_to_role(sender_type: str) -> str:
    return "assistant" if sender_type == "assistant" else "user"


def _title_seed_from_message(message: str) -> str:
    trimmed = (message or "").strip().replace("\n", " ")
    if not trimmed:
        return "New conversation"
    return trimmed[:80]


def _derive_title_if_needed(
    conversation: dict[str, Any], first_message: str
) -> str | None:
    current = conversation.get("title")
    if current and current != "New conversation":
        return None
    return _title_seed_from_message(first_message)
