import json
from redis import asyncio as redis
from src.config import settings
import time

class ContextService:
    def __init__(self):
        self.ttl = 86400 # 24 hours

    def _get_redis(self):
        return redis.from_url(settings.REDIS_URL, decode_responses=True)

    async def get_history(self, chat_id: str) -> list[dict]:
        key = f"chat_context:{chat_id}"
        client = self._get_redis()
        try:
            items = await client.lrange(key, 0, -1)
            messages = [json.loads(i) for i in items]
            return messages
        finally:
            await client.aclose()

    async def add_message(self, chat_id: str, role: str, content: str):
        key = f"chat_context:{chat_id}"
        message = {"role": role, "content": content, "timestamp": time.time()}
        client = self._get_redis()
        try:
            await client.rpush(key, json.dumps(message))
            await client.expire(key, self.ttl)
        finally:
            await client.aclose()

    async def clear_history(self, chat_id: str):
        key = f"chat_context:{chat_id}"
        client = self._get_redis()
        try:
            await client.delete(key)
        finally:
            await client.aclose()

    async def set_ai_enabled(self, chat_id: str, enabled: bool):
        key = f"ai_enabled:{chat_id}"
        client = self._get_redis()
        try:
            if enabled:
                await client.set(key, "1")
            else:
                await client.delete(key)
        finally:
            await client.aclose()

    async def is_ai_enabled(self, chat_id: str) -> bool:
        key = f"ai_enabled:{chat_id}"
        client = self._get_redis()
        try:
            val = await client.get(key)
            return val == "1"
        finally:
            await client.aclose()

    async def add_group_message(self, chat_id: str, sender_name: str, content: str):
        """Store a message from a group chat for later summarization."""
        key = f"group_messages:{chat_id}"
        message = {
            "sender": sender_name,
            "content": content,
            "timestamp": time.time()
        }
        client = self._get_redis()
        try:
            await client.rpush(key, json.dumps(message))
            await client.expire(key, self.ttl)
        finally:
            await client.aclose()

    async def get_group_messages(self, chat_id: str, count: int) -> list[dict]:
        """Retrieve the last N messages from a group chat for summarization."""
        key = f"group_messages:{chat_id}"
        client = self._get_redis()
        try:
            # Get last 'count' messages
            items = await client.lrange(key, -count, -1)
            messages = [json.loads(i) for i in items]
            return messages
        finally:
            await client.aclose()

    async def clear_group_messages(self, chat_id: str):
        """Clear all stored group messages (after summarization or on command)."""
        key = f"group_messages:{chat_id}"
        client = self._get_redis()
        try:
            await client.delete(key)
        finally:
            await client.aclose()

    async def set_transcribe_mode(self, chat_id: str, enabled: bool):
        """Set transcribe-only mode for a chat."""
        key = f"transcribe_mode:{chat_id}"
        client = self._get_redis()
        try:
            if enabled:
                await client.set(key, "1")
            else:
                await client.delete(key)
        finally:
            await client.aclose()

    async def get_transcribe_mode(self, chat_id: str) -> bool:
        """Check if transcribe-only mode is enabled for a chat."""
        key = f"transcribe_mode:{chat_id}"
        client = self._get_redis()
        try:
            val = await client.get(key)
            return val == "1"
        finally:
            await client.aclose()

    # Blacklist management
    async def add_to_blacklist(self, user_id: str, reason: str = ""):
        """Add a user to the blacklist."""
        key = "blacklist"
        client = self._get_redis()
        try:
            await client.hset(key, user_id, reason or "blocked")
        finally:
            await client.aclose()

    async def remove_from_blacklist(self, user_id: str) -> bool:
        """Remove a user from the blacklist. Returns True if user was in blacklist."""
        key = "blacklist"
        client = self._get_redis()
        try:
            result = await client.hdel(key, user_id)
            return result > 0
        finally:
            await client.aclose()

    async def is_blacklisted(self, user_id: str) -> bool:
        """Check if a user is blacklisted."""
        key = "blacklist"
        client = self._get_redis()
        try:
            return await client.hexists(key, user_id)
        finally:
            await client.aclose()

    async def get_blacklist(self) -> dict[str, str]:
        """Get all blacklisted users with reasons."""
        key = "blacklist"
        client = self._get_redis()
        try:
            return await client.hgetall(key)
        finally:
            await client.aclose()

    # Model preference per chat
    async def set_model(self, chat_id: str, model: str):
        """Set preferred LLM model for a chat."""
        key = f"model:{chat_id}"
        client = self._get_redis()
        try:
            await client.set(key, model)
        finally:
            await client.aclose()

    async def get_model(self, chat_id: str) -> str | None:
        """Get preferred LLM model for a chat. Returns None if not set."""
        key = f"model:{chat_id}"
        client = self._get_redis()
        try:
            return await client.get(key)
        finally:
            await client.aclose()


context_service = ContextService()
