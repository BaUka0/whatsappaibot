import json
import time
import logging
import asyncio
from typing import Any
from cachetools import TTLCache
from src.services.supabase_db import supabase_db

logger = logging.getLogger(__name__)

class ContextService:
    def __init__(self):
        self.client = supabase_db.get_client()
        # In-memory deduplication and rate-limiting
        self.dedup_cache = TTLCache(maxsize=10000, ttl=600)  # 10 minutes
        self.ratelimit_cache = TTLCache(maxsize=10000, ttl=60)  # 1 minute

    async def _run_async(self, func, *args, **kwargs) -> Any:
        """Helper to run synchronous Supabase calls in a thread pool."""
        loop = asyncio.get_running_loop()
        # Use partial if kwargs are needed, though run_in_executor only takes *args
        # Simple lambda wrapper handles both
        return await loop.run_in_executor(None, lambda: func(*args, **kwargs))

    async def get_history(self, chat_id: str, limit: int = 20) -> list[dict]:
        """Get chat history from Supabase."""
        try:
            def _fetch():
                return self.client.table("chat_messages") \
                    .select("role, content") \
                    .eq("chat_id", chat_id) \
                    .order("created_at", desc=True) \
                    .limit(limit) \
                    .execute()

            response = await self._run_async(_fetch)
            
            # Reverse to get chronological order
            messages = response.data[::-1]
            return messages
        except Exception as e:
            logger.error(f"Failed to get history from Supabase: {e}")
            return []

    async def add_message(self, chat_id: str, role: str, content: str):
        """Add a message to Supabase."""
        try:
            def _insert():
                self.client.table("chat_messages").insert({
                    "chat_id": chat_id,
                    "role": role,
                    "content": content
                }).execute()

            await self._run_async(_insert)
        except Exception as e:
            logger.error(f"Failed to add message to Supabase: {e}")

    async def clear_history(self, chat_id: str):
        """Clear history for a chat."""
        try:
            def _delete():
                self.client.table("chat_messages").delete().eq("chat_id", chat_id).execute()

            await self._run_async(_delete)
        except Exception as e:
            logger.error(f"Failed to clear history in Supabase: {e}")

    async def set_ai_enabled(self, chat_id: str, enabled: bool):
        """Enable/disable AI for a chat."""
        try:
            def _upsert():
                self.client.table("chat_settings").upsert({
                    "chat_id": chat_id,
                    "ai_enabled": enabled
                }).execute()

            await self._run_async(_upsert)
        except Exception as e:
            logger.error(f"Failed to set AI status in Supabase: {e}")

    async def is_ai_enabled(self, chat_id: str) -> bool:
        """Check if AI is enabled."""
        try:
            def _select():
                return self.client.table("chat_settings") \
                    .select("ai_enabled") \
                    .eq("chat_id", chat_id) \
                    .execute()

            response = await self._run_async(_select)
            if response.data:
                return response.data[0].get("ai_enabled", False)
            return False
        except Exception as e:
            logger.error(f"Failed to check AI status in Supabase: {e}")
            return False

    async def set_transcribe_mode(self, chat_id: str, enabled: bool):
        try:
            def _upsert():
                self.client.table("chat_settings").upsert({
                    "chat_id": chat_id,
                    "transcribe_mode": enabled
                }).execute()

            await self._run_async(_upsert)
        except Exception as e:
            logger.error(f"Failed to set transcribe mode in Supabase: {e}")

    async def get_transcribe_mode(self, chat_id: str) -> bool:
        try:
            def _select():
                return self.client.table("chat_settings") \
                    .select("transcribe_mode") \
                    .eq("chat_id", chat_id) \
                    .execute()

            response = await self._run_async(_select)
            if response.data:
                return response.data[0].get("transcribe_mode", False)
            return False
        except Exception as e:
            logger.error(f"Failed to get transcribe mode in Supabase: {e}")
            return False



    # Blacklist (Using a dedicated table)
    async def is_blacklisted(self, user_id: str) -> bool:
        try:
            def _select():
                return self.client.table("blacklist") \
                    .select("user_id") \
                    .eq("user_id", user_id) \
                    .execute()

            response = await self._run_async(_select)
            return len(response.data) > 0
        except Exception as e:
            logger.error(f"Failed to check blacklist in Supabase: {e}")
            return False

    async def add_to_blacklist(self, user_id: str, reason: str = "blocked"):
        try:
            def _upsert():
                self.client.table("blacklist").upsert({
                    "user_id": user_id,
                    "reason": reason
                }).execute()

            await self._run_async(_upsert)
        except Exception as e:
            logger.error(f"Failed to add to blacklist in Supabase: {e}")

    async def remove_from_blacklist(self, user_id: str) -> bool:
        try:
            def _delete():
                self.client.table("blacklist").delete().eq("user_id", user_id).execute()

            await self._run_async(_delete)
            return True
        except Exception as e:
            logger.error(f"Failed to remove from blacklist in Supabase: {e}")
            return False

    async def get_blacklist(self) -> dict[str, str]:
        try:
            def _select():
                return self.client.table("blacklist").select("*").execute()

            response = await self._run_async(_select)
            return {item["user_id"]: item["reason"] for item in response.data}
        except Exception as e:
            logger.error(f"Failed to get blacklist from Supabase: {e}")
            return {}

    # Deduplication and Rate Limiting (In-memory for single container)
    def check_dedup(self, message_id: str) -> bool:
        if message_id in self.dedup_cache:
            return True
        self.dedup_cache[message_id] = True
        return False

    def check_rate_limit(self, chat_id: str, limit: int = 30) -> bool:
        count = self.ratelimit_cache.get(chat_id, 0)
        if count >= limit:
            return False
        self.ratelimit_cache[chat_id] = count + 1
        return True

    # Group specific (Migration compatibility)
    async def add_group_message(self, chat_id: str, sender_name: str, content: str):
        """Add a group message to context."""
        # We format it to include the sender's name so LLM knows who spoke
        full_content = f"{sender_name}: {content}"
        await self.add_message(chat_id, "user", full_content)

    async def clear_group_messages(self, chat_id: str):
        """Clear group messages."""
        # In single-table architecture, this is redundant if clear_history is also called.
        # But we implement it to satisfy the interface called by worker.py
        pass

context_service = ContextService()
