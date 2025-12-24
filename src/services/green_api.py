import httpx
import os
import logging
from src.config import settings
from dataclasses import dataclass
from typing import Literal

logger = logging.getLogger(__name__)


@dataclass
class Button:
    """Interactive button for WhatsApp messages."""
    button_id: str
    button_text: str
    type: Literal["reply", "copy", "call", "url"] = "reply"
    # Optional fields based on type
    copy_code: str | None = None  # for type="copy"
    phone_number: str | None = None  # for type="call"
    url: str | None = None  # for type="url"
    
    def to_dict(self) -> dict:
        base = {
            "buttonId": self.button_id,
            "buttonText": self.button_text,
            "type": self.type,
        }
        if self.type == "copy" and self.copy_code:
            base["copyCode"] = self.copy_code
        elif self.type == "call" and self.phone_number:
            base["phoneNumber"] = self.phone_number
        elif self.type == "url" and self.url:
            base["url"] = self.url
        return base


class GreenAPIService:
    def __init__(self):
        self.base_url = f"{settings.GREEN_API_HOST}/waInstance{settings.GREEN_API_INSTANCE_ID}"
        self.api_token_url = settings.GREEN_API_TOKEN

        # Media URL for file uploads (uses first 4 digits of instance ID)
        if settings.GREEN_API_MEDIA_HOST:
            self.media_url = f"{settings.GREEN_API_MEDIA_HOST}/waInstance{settings.GREEN_API_INSTANCE_ID}"
        else:
            # Auto-detect: use first 4 digits of instance ID
            instance_prefix = str(settings.GREEN_API_INSTANCE_ID)[:4]
            self.media_url = f"https://{instance_prefix}.api.greenapi.com/waInstance{settings.GREEN_API_INSTANCE_ID}"

    async def health_check(self) -> dict:
        """
        Health check for Green API.
        Returns status dict with 'healthy' bool and 'details' info.
        """
        if not settings.GREEN_API_INSTANCE_ID or not settings.GREEN_API_TOKEN:
            return {
                "healthy": False,
                "details": "Green API credentials not configured"
            }

        try:
            # Simple check - try to get instance info (placeholder endpoint)
            # Green API doesn't have a simple health endpoint, so we check config
            async with httpx.AsyncClient() as client:
                # Use a minimal request to check connectivity
                response = await client.get(
                    f"{self.base_url}/getSettings/{self.api_token_url}",
                    timeout=5
                )
                if response.status_code == 200:
                    return {
                        "healthy": True,
                        "details": "Green API connected"
                    }
                else:
                    return {
                        "healthy": False,
                        "details": f"HTTP {response.status_code}"
                    }
        except httpx.HTTPError as e:
            logger.error(f"Green API health check failed: {e}")
            return {
                "healthy": False,
                "details": f"Connection error: {str(e)}"
            }
        except Exception as e:
            logger.error(f"Green API health check error: {e}")
            return {
                "healthy": False,
                "details": f"Error: {str(e)}"
            }

    async def send_message(self, chat_id: str, message: str):
        """Send a text message to a specific chat."""
        url = f"{self.base_url}/sendMessage/{self.api_token_url}"
        payload = {
            "chatId": chat_id,
            "message": message
        }
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(url, json=payload, timeout=10)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPError as e:
                logger.error(f"Error sending message: {e}")
                return None

    async def send_file_by_url(self, chat_id: str, file_url: str, caption: str = "", file_name: str = "image.png"):
        """
        Send a file (image) by URL.
        https://green-api.com/docs/api/sending/SendFileByUrl/
        Note: URL must not contain special characters like ? = &
        """
        url = f"{self.base_url}/sendFileByUrl/{self.api_token_url}"
        payload = {
            "chatId": chat_id,
            "urlFile": file_url,
            "fileName": file_name,
            "caption": caption
        }
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(url, json=payload, timeout=60)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPError as e:
                logger.error(f"Error sending file by URL: {e}")
                return None

    async def send_file_by_upload(self, chat_id: str, file_path: str, caption: str = "", file_name: str | None = None):
        """
        Send a file by uploading it directly.
        https://green-api.com/docs/api/sending/SendFileByUpload/
        
        This method is more reliable than send_file_by_url for URLs with special characters.
        """
        import os
        
        if not file_name:
            file_name = os.path.basename(file_path)
        
        # Determine MIME type
        ext = os.path.splitext(file_path)[1].lower()
        mime_types = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".gif": "image/gif",
            ".webp": "image/webp",
            ".mp4": "video/mp4",
            ".pdf": "application/pdf",
        }
        mime_type = mime_types.get(ext, "application/octet-stream")
        
        # Use media_url for file uploads (required by Green API)
        url = f"{self.media_url}/sendFileByUpload/{self.api_token_url}"
        
        async with httpx.AsyncClient() as client:
            try:
                with open(file_path, "rb") as f:
                    file_content = f.read()
                
                # Build multipart form
                files = {"file": (file_name, file_content, mime_type)}
                data = {"chatId": chat_id}
                if caption:
                    data["caption"] = caption
                
                response = await client.post(url, data=data, files=files, timeout=60)
                
                if response.status_code != 200:
                    logger.error(f"Upload failed: {response.status_code} - {response.text}")
                    return None

                return response.json()
            except httpx.HTTPError as e:
                logger.error(f"Error uploading file: {e}")
                return None
            except FileNotFoundError:
                logger.error(f"File not found: {file_path}")
                return None

    async def send_interactive_buttons(
        self,
        chat_id: str,
        body: str,
        buttons: list[Button | dict],
        header: str | None = None,
        footer: str | None = None,
    ):
        """
        Send a message with interactive buttons.
        https://green-api.com/docs/api/sending/SendInteractiveButtons/
        
        Limits:
        - Max 3 buttons per message
        - Max 25 characters per button text
        
        Args:
            chat_id: Chat ID
            body: Main message text
            buttons: List of Button objects or dicts
            header: Optional header text
            footer: Optional footer text
        """
        url = f"{self.base_url}/sendInteractiveButtons/{self.api_token_url}"
        
        # Convert Button objects to dicts if needed
        button_list = []
        for btn in buttons[:3]:  # Max 3 buttons
            if isinstance(btn, Button):
                button_list.append(btn.to_dict())
            else:
                button_list.append(btn)
        
        payload = {
            "chatId": chat_id,
            "body": body,
            "buttons": button_list,
        }
        if header:
            payload["header"] = header
        if footer:
            payload["footer"] = footer
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(url, json=payload, timeout=10)
                response.raise_for_status()
                result = response.json()
                logger.info(f"Interactive buttons response: {result}")
                return result
            except httpx.HTTPError as e:
                logger.error(f"Error sending interactive buttons: {e}")
                # Fallback to regular message
                fallback_msg = f"{header or ''}\n\n{body}\n\n{footer or ''}"
                return await self.send_message(chat_id, fallback_msg.strip())

    async def download_file(self, url: str, file_path: str):
        """Download file from URL to local path."""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, timeout=30)
                response.raise_for_status()
                with open(file_path, "wb") as f:
                    f.write(response.content)
                return file_path
            except httpx.HTTPError as e:
                logger.error(f"Error downloading file: {e}")
                return None

    async def get_chat_history(self, chat_id: str, count: int = 100) -> list[dict]:
        """
        Get chat message history from Green API.
        https://green-api.com/docs/api/journals/GetChatHistory/
        """
        url = f"{self.base_url}/getChatHistory/{self.api_token_url}"
        payload = {
            "chatId": chat_id,
            "count": count
        }
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(url, json=payload, timeout=30)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPError as e:
                logger.error(f"Error getting chat history: {e}")
                return []

    async def get_message(self, chat_id: str, id_message: str) -> dict | None:
        """
        Get a specific message by ID from Green API.
        https://green-api.com/docs/api/journals/GetMessage/
        """
        url = f"{self.base_url}/getMessage/{self.api_token_url}"
        payload = {
            "chatId": chat_id,
            "idMessage": id_message
        }
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(url, json=payload, timeout=30)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPError as e:
                logger.error(f"Error getting message: {e}")
                return None


green_api = GreenAPIService()
