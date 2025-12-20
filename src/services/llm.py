import base64
import os
import httpx
from openai import AsyncOpenAI
from src.config import settings


# Cache for available models (refreshed on startup or when needed)
_cached_models: dict[str, str] = {}


async def fetch_available_models() -> dict[str, str]:
    """Fetch available models from Groq API."""
    global _cached_models
    
    if _cached_models:
        return _cached_models
    
    url = "https://api.groq.com/openai/v1/models"
    headers = {
        "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            models = {}
            for model in data.get("data", []):
                model_id = model.get("id", "")
                # Filter only chat models (skip whisper, embeddings, etc.)
                if model_id and not any(x in model_id for x in ["whisper", "embed", "guard", "tool"]):
                    # Create friendly description
                    owned_by = model.get("owned_by", "")
                    context = model.get("context_window", 0)
                    desc = f"{owned_by} | {context // 1000}k контекст" if context else owned_by
                    models[model_id] = desc
            
            _cached_models = models
            print(f"Loaded {len(models)} models from Groq API")
            return models
            
    except Exception as e:
        print(f"Failed to fetch models: {e}")
        # Return fallback models
        return {
            "llama-3.3-70b-versatile": "Llama 3.3 70B (умный)",
            "llama-3.1-70b-versatile": "Llama 3.1 70B",
            "gemma2-9b-it": "Gemma 2 9B",
            "mixtral-8x7b-32768": "Mixtral 8x7B",
        }


def get_cached_models() -> dict[str, str]:
    """Get cached models (synchronous, for imports)."""
    return _cached_models


# Alias for backwards compatibility
AVAILABLE_MODELS = _cached_models


class LLMService:
    def __init__(self):
        self.api_key = settings.OPENROUTER_API_KEY
        self.default_model = settings.OPENROUTER_MODEL
        self.base_url = settings.OPENROUTER_BASE_URL
        self.system_prompt = settings.SYSTEM_PROMPT
        
        self.client = AsyncOpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
        )

    async def get_available_models(self) -> dict[str, str]:
        """Get available models (fetches from API if not cached)."""
        return await fetch_available_models()

    async def get_response(self, messages: list[dict], model: str | None = None) -> str:
        """
        Get response from LLM.
        
        Args:
            messages: Chat messages
            model: Optional model override (uses default if not specified)
        """
        use_model = model or self.default_model
        
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
                        for file_item in content["files"]:
                            file_path = file_item
                            if isinstance(file_item, dict):
                                file_path = file_item.get("path")
                            
                            if not file_path or not os.path.exists(file_path):
                                continue
                                
                            ext = os.path.splitext(file_path)[1].lower()
                            if ext in [".jpg", ".jpeg", ".png", ".webp"]:
                                with open(file_path, "rb") as image_file:
                                    base64_image = base64.b64encode(image_file.read()).decode('utf-8')
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
            print(f"LLM Error ({use_model}): {e}")
            return f"Ошибка модели {use_model}. Попробуйте /model для списка."


llm_service = LLMService()
