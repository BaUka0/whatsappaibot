import json
import time
import logging
from cachetools import TTLCache
from src.services.supabase_db import supabase_db

logger = logging.getLogger(__name__)

class ContextService:
    def __init__(self):
        self.client = supabase_db.get_client()
        # In-memory deduplication and rate-limiting
        self.dedup_cache = TTLCache(maxsize=10000, ttl=600)  # 10 minutes
        self.ratelimit_cache = TTLCache(maxsize=10000, ttl=60)  # 1 minute

    async def get_history(self, chat_id: str, limit: int = 20) -> list[dict]:
        """Get chat history from Supabase."""
        try:
            response = self.client.table("chat_messages") \
                .select("role, content") \
                .eq("chat_id", chat_id) \
                .order("created_at", desc=True) \
                .limit(limit) \
                .execute()
            
            # Reverse to get chronological order
            messages = response.data[::-1]
            return messages
        except Exception as e:
            logger.error(f"Failed to get history from Supabase: {e}")
            return []

    async def add_message(self, chat_id: str, role: str, content: str):
        """Add a message to Supabase."""
        try:
            self.client.table("chat_messages").insert({
                "chat_id": chat_id,
                "role": role,
                "content": content
            }).execute()
        except Exception as e:
            logger.error(f"Failed to add message to Supabase: {e}")

    async def clear_history(self, chat_id: str):
        """Clear history for a chat."""
        try:
            self.client.table("chat_messages").delete().eq("chat_id", chat_id).execute()
        except Exception as e:
            logger.error(f"Failed to clear history in Supabase: {e}")

    async def set_ai_enabled(self, chat_id: str, enabled: bool):
        """Enable/disable AI for a chat."""
        try:
            self.client.table("chat_settings").upsert({
                "chat_id": chat_id,
                "ai_enabled": enabled
            }).execute()
        except Exception as e:
            logger.error(f"Failed to set AI status in Supabase: {e}")

    async def is_ai_enabled(self, chat_id: str) -> bool:
        """Check if AI is enabled."""
        try:
            response = self.client.table("chat_settings") \
                .select("ai_enabled") \
                .eq("chat_id", chat_id) \
                .execute()
            if response.data:
                return response.data[0].get("ai_enabled", False)
            return False
        except Exception as e:
            logger.error(f"Failed to check AI status in Supabase: {e}")
            return False

    async def set_transcribe_mode(self, chat_id: str, enabled: bool):
        try:
            self.client.table("chat_settings").upsert({
                "chat_id": chat_id,
                "transcribe_mode": enabled
            }).execute()
        except Exception as e:
            logger.error(f"Failed to set transcribe mode in Supabase: {e}")

    async def get_transcribe_mode(self, chat_id: str) -> bool:
        try:
            response = self.client.table("chat_settings") \
                .select("transcribe_mode") \
                .eq("chat_id", chat_id) \
                .execute()
            if response.data:
                return response.data[0].get("transcribe_mode", False)
            return False
        except Exception as e:
            logger.error(f"Failed to get transcribe mode in Supabase: {e}")
            return False

    async def set_model(self, chat_id: str, model: str):
        try:
            self.client.table("chat_settings").upsert({
                "chat_id": chat_id,
                "preferred_model": model
            }).execute()
        except Exception as e:
            logger.error(f"Failed to set model in Supabase: {e}")

    async def get_model(self, chat_id: str) -> str | None:
        try:
            response = self.client.table("chat_settings") \
                .select("preferred_model") \
                .eq("chat_id", chat_id) \
                .execute()
            if response.data:
                return response.data[0].get("preferred_model")
            return None
        except Exception as e:
            logger.error(f"Failed to get model from Supabase: {e}")
            return None

    # Blacklist (Using a dedicated table)
    async def is_blacklisted(self, user_id: str) -> bool:
        try:
            response = self.client.table("blacklist") \
                .select("user_id") \
                .eq("user_id", user_id) \
                .execute()
            return len(response.data) > 0
        except Exception as e:
            logger.error(f"Failed to check blacklist in Supabase: {e}")
            return False

    async def add_to_blacklist(self, user_id: str, reason: str = "blocked"):
        try:
            self.client.table("blacklist").upsert({
                "user_id": user_id,
                "reason": reason
            }).execute()
        except Exception as e:
            logger.error(f"Failed to add to blacklist in Supabase: {e}")

    async def remove_from_blacklist(self, user_id: str) -> bool:
        try:
            self.client.table("blacklist").delete().eq("user_id", user_id).execute()
            return True
        except Exception as e:
            logger.error(f"Failed to remove from blacklist in Supabase: {e}")
            return False

    async def get_blacklist(self) -> dict[str, str]:
        try:
            response = self.client.table("blacklist").select("*").execute()
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

context_service = ContextService()
