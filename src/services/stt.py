"""
Speech-to-Text service using Groq Whisper API.
Includes Redis caching to avoid repeated transcriptions.
"""
from abc import ABC, abstractmethod
import os
import hashlib
from openai import AsyncOpenAI
from src.config import settings
import subprocess


class STTProvider(ABC):
    @abstractmethod
    async def transcribe(self, file_path: str) -> str:
        pass


class CachedSTT(STTProvider):
    """Wrapper that caches transcriptions in Redis."""
    
    def __init__(self, provider: STTProvider):
        self.provider = provider
        self._redis = None
    
    def _get_redis(self):
        if self._redis is None:
            import redis.asyncio as redis_lib
            self._redis = redis_lib.from_url(settings.REDIS_URL, decode_responses=True)
        return self._redis
    
    def _get_file_hash(self, file_path: str) -> str:
        """Get MD5 hash of file content for cache key."""
        hasher = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                hasher.update(chunk)
        return hasher.hexdigest()
    
    async def transcribe(self, file_path: str) -> str:
        if not os.path.exists(file_path):
            return ""
        
        file_hash = self._get_file_hash(file_path)
        cache_key = f"stt_cache:{file_hash}"
        
        redis = self._get_redis()
        try:
            cached = await redis.get(cache_key)
            if cached:
                print(f"STT cache hit for {file_hash[:8]}...")
                return cached
        except Exception as e:
            print(f"Redis cache error: {e}")
        
        result = await self.provider.transcribe(file_path)
        
        if result:
            try:
                await redis.set(cache_key, result, ex=86400)  # 24 hours
            except Exception as e:
                print(f"Redis cache set error: {e}")
        
        return result


def _convert_to_mp3(input_path: str) -> str:
    """Convert audio file to MP3 format using FFmpeg."""
    if input_path.endswith(".mp3"):
        return input_path
    
    output_path = f"{os.path.splitext(input_path)[0]}.mp3"
    try:
        subprocess.run(
            ["ffmpeg", "-i", input_path, "-y", output_path],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        return output_path
    except subprocess.CalledProcessError as e:
        print(f"FFmpeg conversion failed: {e}")
        return input_path


class GroqSTT(STTProvider):
    """Groq Whisper - very fast, generous free tier."""
    
    def __init__(self):
        self.client = AsyncOpenAI(
            api_key=settings.OPENROUTER_API_KEY,
            base_url="https://api.groq.com/openai/v1",
        )

    async def transcribe(self, file_path: str) -> str:
        if not settings.OPENROUTER_API_KEY:
            return "STT не настроен (нужен API ключ)."
        
        converted_path = _convert_to_mp3(file_path)
        
        try:
            with open(converted_path, "rb") as audio_file:
                transcription = await self.client.audio.transcriptions.create(
                    model="whisper-large-v3-turbo",
                    file=audio_file,
                )
            return transcription.text
        except Exception as e:
            print(f"Groq STT Error: {e}")
            return ""
        finally:
            if converted_path != file_path and os.path.exists(converted_path):
                os.remove(converted_path)


def get_stt_provider() -> STTProvider:
    """Get STT provider with caching enabled."""
    return CachedSTT(GroqSTT())
