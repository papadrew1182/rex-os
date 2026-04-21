"""Dispatcher — composition root that assembles the AI spine per request."""

from __future__ import annotations

from dataclasses import dataclass

import asyncpg

from app.repositories.catalog_repository import CatalogRepository
from app.repositories.chat_repository import ChatRepository
from app.repositories.prompt_repository import PromptRepository
from app.services.ai.catalog_service import CatalogService
from app.services.ai.chat_service import ChatService
from app.services.ai.context_builder import ContextBuilder
from app.services.ai.followups import FollowupGenerator
from app.services.ai.model_client import ModelClient, get_model_client
from app.services.ai.prompt_registry import PromptRegistryService
from app.services.ai.sql_planner import SqlPlanner


@dataclass
class AssistantDispatcher:
    pool: asyncpg.Pool
    model_client: ModelClient

    chat_repo: ChatRepository = None  # type: ignore[assignment]
    prompt_repo: PromptRepository = None  # type: ignore[assignment]
    catalog_repo: CatalogRepository = None  # type: ignore[assignment]
    catalog_service: CatalogService = None  # type: ignore[assignment]
    prompt_registry: PromptRegistryService = None  # type: ignore[assignment]
    context_builder: ContextBuilder = None  # type: ignore[assignment]
    followup_generator: FollowupGenerator = None  # type: ignore[assignment]
    chat_service: ChatService = None  # type: ignore[assignment]
    sql_planner: SqlPlanner = None  # type: ignore[assignment]

    @classmethod
    def build(cls, pool: asyncpg.Pool) -> "AssistantDispatcher":
        chat_repo = ChatRepository(pool)
        prompt_repo = PromptRepository(pool)
        catalog_repo = CatalogRepository(pool)
        model_client = get_model_client()

        instance = cls(pool=pool, model_client=model_client)
        instance.chat_repo = chat_repo
        instance.prompt_repo = prompt_repo
        instance.catalog_repo = catalog_repo
        instance.catalog_service = CatalogService(catalog_repo)
        instance.prompt_registry = PromptRegistryService(prompt_repo)
        instance.context_builder = ContextBuilder()
        instance.followup_generator = FollowupGenerator()
        instance.chat_service = ChatService(
            chat_repo=chat_repo,
            model_client=model_client,
            followup_generator=instance.followup_generator,
            pool=pool,
        )
        instance.sql_planner = SqlPlanner(pool)
        return instance
