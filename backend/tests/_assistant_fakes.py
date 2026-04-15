"""Shared test doubles for the Session 1 AI spine."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, AsyncIterator
from uuid import UUID, uuid4

from app.services.ai.catalog_service import CatalogService  # noqa: F401
from app.services.ai.chat_service import ChatService
from app.services.ai.context_builder import ContextBuilder
from app.services.ai.followups import FollowupGenerator
from app.services.ai.model_client import ModelClient, ModelRequest
from app.services.ai.prompt_registry import PromptRegistryService  # noqa: F401


class FakeChatRepository:
    def __init__(self) -> None:
        self.conversations: dict[UUID, dict[str, Any]] = {}
        self.messages: dict[UUID, list[dict[str, Any]]] = {}

    async def create_conversation(
        self, *, user_id, title, project_id, active_action_slug,
        page_context, conversation_metadata=None,
    ) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        cid = uuid4()
        row = {
            "id": cid,
            "user_id": user_id,
            "title": title,
            "project_id": project_id,
            "active_action_slug": active_action_slug,
            "page_context": page_context or {},
            "conversation_metadata": conversation_metadata or {},
            "created_at": now,
            "updated_at": now,
            "last_message_at": now,
            "archived_at": None,
        }
        self.conversations[cid] = row
        self.messages[cid] = []
        return dict(row)

    async def get_conversation(self, conversation_id, *, user_id):
        row = self.conversations.get(conversation_id)
        if row is None or row["user_id"] != user_id or row["archived_at"]:
            return None
        return dict(row)

    async def list_conversations(self, *, user_id, limit=50):
        items: list[dict[str, Any]] = []
        for row in self.conversations.values():
            if row["user_id"] != user_id or row["archived_at"]:
                continue
            msgs = self.messages.get(row["id"], [])
            preview = msgs[-1]["content"][:160] if msgs else None
            items.append(
                {
                    "id": row["id"],
                    "title": row["title"],
                    "project_id": row["project_id"],
                    "active_action_slug": row["active_action_slug"],
                    "last_message_preview": preview,
                    "last_message_at": row["last_message_at"],
                    "updated_at": row["updated_at"],
                }
            )
        items.sort(key=lambda r: r["last_message_at"], reverse=True)
        return items[:limit]

    async def archive_conversation(self, conversation_id, *, user_id) -> bool:
        row = self.conversations.get(conversation_id)
        if row is None or row["user_id"] != user_id or row["archived_at"]:
            return False
        row["archived_at"] = datetime.now(timezone.utc)
        return True

    async def touch_conversation(self, conversation_id, *, title=None, active_action_slug=None):
        row = self.conversations.get(conversation_id)
        if row is None:
            return
        row["last_message_at"] = datetime.now(timezone.utc)
        if title:
            row["title"] = title
        if active_action_slug:
            row["active_action_slug"] = active_action_slug

    async def append_message(
        self, *, conversation_id, sender_type, content,
        content_format="markdown", structured_payload=None, citations=None,
        model_key=None, prompt_key=None, token_usage=None,
    ):
        mid = uuid4()
        row = {
            "id": mid,
            "conversation_id": conversation_id,
            "sender_type": sender_type,
            "content": content,
            "content_format": content_format,
            "structured_payload": structured_payload or {},
            "citations": citations or [],
            "model_key": model_key,
            "prompt_key": prompt_key,
            "token_usage": token_usage or {},
            "created_at": datetime.now(timezone.utc),
        }
        self.messages.setdefault(conversation_id, []).append(row)
        return dict(row)

    async def list_messages(self, conversation_id, *, limit=500):
        return [dict(m) for m in self.messages.get(conversation_id, [])][:limit]


class FakeCatalogService:
    def __init__(self, response) -> None:
        self._response = response

    async def build_catalog_response(self, *, role_keys=None):
        return self._response


class FakePromptRegistry:
    async def get_system_base(self) -> str:
        return "You are Rex (test prompt)."


class DeterministicModelClient:
    model_key = "echo-test"

    async def stream_completion(self, request: ModelRequest) -> AsyncIterator[str]:
        for chunk in ["Hello ", "from ", "the fake model."]:
            yield chunk

    async def complete(self, request: ModelRequest) -> str:
        return "Hello from the fake model."


@dataclass
class FakeDispatcher:
    chat_repo: FakeChatRepository
    catalog_service: FakeCatalogService
    prompt_registry: FakePromptRegistry
    context_builder: ContextBuilder
    followup_generator: FollowupGenerator
    chat_service: ChatService
    model_client: ModelClient

    @classmethod
    def build(cls, catalog_response) -> "FakeDispatcher":
        chat_repo = FakeChatRepository()
        model_client = DeterministicModelClient()
        followups = FollowupGenerator()
        return cls(
            chat_repo=chat_repo,
            catalog_service=FakeCatalogService(catalog_response),
            prompt_registry=FakePromptRegistry(),
            context_builder=ContextBuilder(),
            followup_generator=followups,
            chat_service=ChatService(
                chat_repo=chat_repo,
                model_client=model_client,
                followup_generator=followups,
            ),
            model_client=model_client,
        )
