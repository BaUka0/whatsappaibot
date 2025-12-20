import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # App Settings
    APP_NAME: str = "WhatsApp AI Bot"
    LOG_LEVEL: str = "INFO"
    
    # Green API
    GREEN_API_INSTANCE_ID: str
    GREEN_API_TOKEN: str
    GREEN_API_HOST: str = "https://api.green-api.com"
    # Media host for file uploads (format: https://XXXX.api.greenapi.com where XXXX is first 4 digits of instance)
    GREEN_API_MEDIA_HOST: str | None = None

    # LLM Settings
    OPENROUTER_API_KEY: str
    OPENROUTER_MODEL: str = "llama-3.3-70b-versatile"
    OPENROUTER_BASE_URL: str = "https://api.groq.com/openai/v1"
    SYSTEM_PROMPT: str = """You are a helpful WhatsApp assistant. 
IMPORTANT: Always respond in the SAME LANGUAGE the user writes to you.
- If user writes in Russian, respond in Russian.
- If user writes in English, respond in English.
- If user writes in Kazakh, respond in Kazakh.
- And so on for any language.

You can understand voice messages (transcribed) and see images. Be concise but helpful."""
    
    # Summarization
    SUMMARY_MESSAGE_COUNT: int = 50
    SUMMARY_PROMPT: str = "Ты получаешь историю сообщений из группового чата. Создай краткое, структурированное резюме обсуждения. Выдели ключевые темы, решения и важные моменты. Отвечай на русском языке."
    
    # Bot Settings
    BOT_NICKNAME: str = "ботяра"  # Trigger word for the bot in group chats
    ADMIN_CHAT_ID: str | None = None  # Admin's chat ID for admin commands

    # Redis & Celery
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/0"

    # Paths
    MEDIA_DIR: str = os.path.join(os.getcwd(), "media")

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()

# Ensure media directory exists
os.makedirs(settings.MEDIA_DIR, exist_ok=True)
