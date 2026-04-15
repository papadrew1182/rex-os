"""Assistant router — the frozen contract for Session 3 to consume.

Endpoints:

    GET    /api/assistant/catalog
    GET    /api/assistant/conversations
    GET    /api/assistant/conversations/{conversation_id}
    POST   /api/assistant/chat                       (SSE)
    DELETE /api/assistant/conversations/{conversation_id}

Auth: reuses ``app.dependencies.get_current_user`` so the existing test
harness continues to work. Legacy-to-canonical role normalization
happens inside the dispatcher's ``ContextBuilder``.
"""

from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

import db as rex_db
from app.dependencies import get_current_user
from app.models.foundation import UserAccount
from app.schemas.assistant import AssistantChatRequest, AssistantUser
from app.schemas.catalog import CatalogResponse
from app.schemas.chat import (
    ChatConversation,
    ChatConversationSummary,
    ChatMessage,
    ConversationDetailResponse,
    ConversationListResponse,
)
from app.services.ai.dispatcher import AssistantDispatcher

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/assistant", tags=["assistant"])


async def _get_dispatcher(request: Request) -> AssistantDispatcher:
    cached = getattr(request.app.state, "assistant_dispatcher", None)
    if cached is not None:
        return cached
    pool = await rex_db.get_pool()
    dispatcher = AssistantDispatcher.build(pool)
    request.app.state.assistant_dispatcher = dispatcher
    return dispatcher


async def _build_assistant_user(
    dispatcher: AssistantDispatcher, user: UserAccount
) -> AssistantUser:
    return dispatcher.context_builder.build_user(
        user_id=user.id,
        email=getattr(user, "email", None),
        full_name=None,
        legacy_role=getattr(user, "global_role", None),
    )


@router.get("/catalog", response_model=CatalogResponse)
async def get_catalog(
    request: Request,
    user: UserAccount = Depends(get_current_user),
) -> CatalogResponse:
    dispatcher = await _get_dispatcher(request)
    assistant_user = await _build_assistant_user(dispatcher, user)
    return await dispatcher.catalog_service.build_catalog_response(
        role_keys=assistant_user.role_keys,
    )


@router.get("/conversations", response_model=ConversationListResponse)
async def list_conversations(
    request: Request,
    user: UserAccount = Depends(get_current_user),
) -> ConversationListResponse:
    dispatcher = await _get_dispatcher(request)
    rows = await dispatcher.chat_repo.list_conversations(user_id=user.id)
    return ConversationListResponse(
        items=[ChatConversationSummary(**row) for row in rows]
    )


@router.get(
    "/conversations/{conversation_id}",
    response_model=ConversationDetailResponse,
)
async def get_conversation(
    conversation_id: UUID,
    request: Request,
    user: UserAccount = Depends(get_current_user),
) -> ConversationDetailResponse:
    dispatcher = await _get_dispatcher(request)
    conversation = await dispatcher.chat_repo.get_conversation(
        conversation_id, user_id=user.id
    )
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    message_rows = await dispatcher.chat_repo.list_messages(conversation_id)
    return ConversationDetailResponse(
        conversation=ChatConversation(**conversation),
        messages=[ChatMessage(**row) for row in message_rows],
    )


@router.delete("/conversations/{conversation_id}", status_code=204)
async def archive_conversation(
    conversation_id: UUID,
    request: Request,
    user: UserAccount = Depends(get_current_user),
) -> None:
    dispatcher = await _get_dispatcher(request)
    ok = await dispatcher.chat_repo.archive_conversation(
        conversation_id, user_id=user.id
    )
    if not ok:
        raise HTTPException(status_code=404, detail="Conversation not found")


@router.post("/chat")
async def post_chat(
    payload: AssistantChatRequest,
    request: Request,
    user: UserAccount = Depends(get_current_user),
) -> StreamingResponse:
    dispatcher = await _get_dispatcher(request)
    assistant_user = await _build_assistant_user(dispatcher, user)

    system_prompt = await dispatcher.prompt_registry.get_system_base()
    context = dispatcher.context_builder.build_context(
        user=assistant_user,
        project_id=payload.project_id,
        page_context=payload.page_context,
        system_prompt=system_prompt,
    )

    stream = dispatcher.chat_service.stream_chat(
        request=payload,
        user=assistant_user,
        context=context,
    )

    return StreamingResponse(
        stream,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
