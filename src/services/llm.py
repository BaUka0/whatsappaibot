import base64
import os
import httpx
import logging
import asyncio
from openai import AsyncOpenAI
from src.config import settings

logger = logging.getLogger(__name__)


async def encode_image_to_base64(file_path: str) -> str | None:
    """
    Asynchronously encode an image file to base64.
    Uses run_in_executor to avoid blocking the event loop.
    """
    if not file_path or not os.path.exists(file_path):
        return None

    def _read_and_encode():
        with open(file_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')

    loop = asyncio.get_event_loop()
    try:
        return await loop.run_in_executor(None, _read_and_encode)
    except Exception as e:
        logger.error(f"Failed to encode image {file_path}: {e}")
        return None


class LLMService:
    def __init__(self):
        self.api_key = settings.LLM_API_KEY
        self.default_model = settings.LLM_MODEL
        self.base_url = settings.LLM_BASE_URL
        self.system_prompt = settings.SYSTEM_PROMPT

        self.client = AsyncOpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
        )

    async def health_check(self) -> dict:
        """
        Health check for LLM API.
        """
        try:
            # We just try a dry-run list models or similar if possible. 
            # Or just check if client is configured.
            if not self.api_key:
                 return {"healthy": False, "details": "LLM API Key missing"}
            
            return {
                "healthy": True,
                "details": f"LLM configured with {self.default_model}"
            }
        except Exception as e:
            return {
                "healthy": False,
                "details": f"Error: {str(e)}"
            }

    async def get_response(self, messages: list[dict], model: str | None = None) -> str:
        """
        Get response from LLM.
        
        Args:
            messages: Chat messages
            model: IGNORED (kept for signature compatibility, but we always use config model)
        """
        # Always use the configured model, ignoring granular overrides
        use_model = self.default_model

        # Validate API key
        if not self.api_key:
            logger.error("LLM API key not configured")
            return "Ошибка конфигурации: API ключ не настроен"

        try:
            formatted_messages = []
            system_instruction = self.system_prompt
            first_user_message_processed = False
            
            for msg in messages:
                role = msg["role"]
                if role == "system":
                    system_instruction = msg["content"]
                    continue
                
                content = msg["content"]
                
                if isinstance(content, str):
                    if role == "user" and not first_user_message_processed and system_instruction:
                        content = f"{system_instruction}\n\n---\n\n{content}"
                        first_user_message_processed = True
                    formatted_messages.append({"role": role, "content": content})
                    
                elif isinstance(content, dict):
                    openai_content = []
                    text_part = content.get("text", "")
                    
                    if role == "user" and not first_user_message_processed and system_instruction:
                        text_part = f"{system_instruction}\n\n---\n\n{text_part}"
                        first_user_message_processed = True
                    
                    if text_part:
                        openai_content.append({"type": "text", "text": text_part})
                    
                    if "files" in content:
                        # Gather all file encoding tasks
                        encode_tasks = []
                        for file_item in content["files"]:
                            file_path = file_item
                            if isinstance(file_item, dict):
                                file_path = file_item.get("path")

                            if not file_path or not os.path.exists(file_path):
                                continue

                            ext = os.path.splitext(file_path)[1].lower()
                            if ext in [".jpg", ".jpeg", ".png", ".webp"]:
                                encode_tasks.append((file_path, ext))

                        # Process all encodings concurrently
                        for file_path, ext in encode_tasks:
                            base64_image = await encode_image_to_base64(file_path)
                            if base64_image:
                                mime_type = "image/jpeg" if ext in [".jpg", ".jpeg"] else f"image/{ext[1:]}"
                                openai_content.append({
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:{mime_type};base64,{base64_image}"
                                    }
                                })

                    formatted_messages.append({"role": role, "content": openai_content})

            response = await self.client.chat.completions.create(
                model=use_model,
                messages=formatted_messages,
                extra_headers={
                    "HTTP-Referer": "https://github.com/green-api/whatsapp-ai-bot",
                    "X-Title": "WhatsApp AI Bot",
                }
            )
            
            return response.choices[0].message.content

        except Exception as e:
            logger.error(f"LLM Error ({use_model}): {e}")
            return f"Ошибка AI: {str(e)}"


llm_service = LLMService()
