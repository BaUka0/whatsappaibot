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
    # Media host for file uploads
    GREEN_API_MEDIA_HOST: str | None = None

    # Supabase Settings
    SUPABASE_URL: str
    SUPABASE_KEY: str

    # LLM Settings
    LLM_API_KEY: str
    LLM_MODEL: str = "gpt-3.5-turbo" # Default, user should override
    LLM_BASE_URL: str = "https://api.openai.com/v1"
    
    # Text-to-Speech / STT (Groq)
    GROQ_API_KEY: str
    
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

    # Paths
    MEDIA_DIR: str = os.path.join(os.getcwd(), "media")

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()

# Ensure media directory exists
os.makedirs(settings.MEDIA_DIR, exist_ok=True)
