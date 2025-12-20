"""
Message handlers for different message types.
Extracted from worker.py for better organization.
"""
import os
import logging
from src.config import settings
from src.services.green_api import green_api
from src.services.stt import get_stt_provider
from src.services.context import context_service

logger = logging.getLogger(__name__)


async def handle_text_message(message_data: dict) -> tuple[str, None]:
    """Extract text from text message."""
    text = message_data.get("textMessageData", {}).get("textMessage", "")
    return text, None


async def handle_extended_text_message(message_data: dict, chat_id: str) -> tuple[str, str | None]:
    """
    Handle extended text message (may include quoted message).
    Returns (text_content, quoted_context).
    """
    extended_data = message_data.get("extendedTextMessageData", {})
    text_content = extended_data.get("text", "")
    quoted_context = None
    
    # Check for quoted message (reply)
    quoted_msg = extended_data.get("quotedMessage", {})
    if quoted_msg:
        quoted_context = await _process_quoted_message(quoted_msg, chat_id)
    
    return text_content, quoted_context


async def handle_quoted_message(message_data: dict, chat_id: str) -> tuple[str, str | None]:
    """
    Handle quotedMessage type (reply to a message).
    Returns (text_content, quoted_context).
    """
    extended_data = message_data.get("extendedTextMessageData", {})
    text_content = extended_data.get("text", "")
    quoted_context = None
    
    quoted_msg = message_data.get("quotedMessage", {})
    if quoted_msg:
        quoted_context = await _process_quoted_message(quoted_msg, chat_id)
    
    return text_content, quoted_context


async def _process_quoted_message(quoted_msg: dict, chat_id: str) -> str | None:
    """Process a quoted message and return context string."""
    quoted_stanza_id = quoted_msg.get("stanzaId")
    quoted_type = quoted_msg.get("typeMessage", "")
    
    logger.info(f"Quoted message detected: type={quoted_type}, stanzaId={quoted_stanza_id}")
    
    # Handle quoted audio/voice messages
    if quoted_type in ["audioMessage", "voiceMessage"] and quoted_stanza_id:
        return await _transcribe_quoted_audio(chat_id, quoted_stanza_id)
    
    # Handle quoted text messages
    elif quoted_type == "textMessage":
        quoted_text = quoted_msg.get("textMessage", "")
        if quoted_text:
            return f"[Цитируемое сообщение]: {quoted_text}"
    
    elif quoted_type == "extendedTextMessage":
        quoted_text = quoted_msg.get("extendedTextMessage", {}).get("text", "") or quoted_msg.get("textMessage", "")
        if quoted_text:
            return f"[Цитируемое сообщение]: {quoted_text}"
    
    return None


async def _transcribe_quoted_audio(chat_id: str, stanza_id: str) -> str:
    """Fetch and transcribe a quoted audio message."""
    original_msg = await green_api.get_message(chat_id, stanza_id)
    
    if not original_msg:
        logger.warning(f"Could not fetch original message {stanza_id}")
        return "[Голосовое сообщение]"
    
    download_url = original_msg.get("downloadUrl", "")
    logger.info(f"Got original message, downloadUrl: {download_url[:50] if download_url else 'empty'}...")
    
    if not download_url:
        return "[Голосовое сообщение - URL недоступен]"
    
    try:
        file_name = f"quoted_{chat_id}_{stanza_id}.ogg"
        file_path = os.path.join(settings.MEDIA_DIR, file_name)
        
        await green_api.download_file(download_url, file_path)
        
        stt = get_stt_provider()
        transcription = await stt.transcribe(file_path)
        
        # Cleanup
        if os.path.exists(file_path):
            os.remove(file_path)
        
        if transcription:
            sender_name = original_msg.get("senderName", "Кто-то")
            logger.info(f"Transcribed quoted audio: {transcription[:100]}...")
            return f"[Голосовое сообщение от {sender_name}]: {transcription}"
        else:
            return "[Голосовое сообщение - не удалось распознать]"
    except Exception as e:
        logger.error(f"Failed to transcribe quoted audio: {e}")
        return "[Голосовое сообщение]"


async def handle_audio_message(message_data: dict, chat_id: str) -> tuple[str, bool]:
    """
    Handle audio/voice message. Downloads and transcribes.
    Returns (text_content, should_skip_llm).
    
    If transcribe mode is enabled, returns (transcription, True).
    """
    file_url = message_data.get("fileMessageData", {}).get("downloadUrl")
    if not file_url:
        return "(Не удалось получить голосовое)", False
    
    file_name = f"{chat_id}_{message_data.get('idMessage')}.ogg"
    file_path = os.path.join(settings.MEDIA_DIR, file_name)
    
    # Download
    await green_api.download_file(file_url, file_path)
    
    # STT
    stt = get_stt_provider()
    logger.info(f"Calling STT provider for file: {file_path}")
    transcription = await stt.transcribe(file_path)
    
    # Cleanup
    if os.path.exists(file_path):
        os.remove(file_path)
    
    if not transcription:
        return "(Не удалось распознать голосовое сообщение)", False
    
    # Check transcribe-only mode
    transcribe_mode = await context_service.get_transcribe_mode(chat_id)
    if transcribe_mode:
        await green_api.send_message(chat_id, f"🎙️ *Транскрибация:*\n\n{transcription}")
        return transcription, True  # Skip LLM
    
    return f"Пользователь отправил голосовое сообщение. Текст: {transcription}", False


async def handle_image_message(message_data: dict, chat_id: str) -> tuple[str, dict | None, str | None]:
    """
    Handle image message.
    Returns (text_content, structured_content, file_path).
    """
    file_url = message_data.get("fileMessageData", {}).get("downloadUrl")
    if not file_url:
        return "Пользователь прислал изображение.", None, None
    
    file_name = f"{chat_id}_{message_data.get('idMessage')}.jpg"
    file_path = os.path.join(settings.MEDIA_DIR, file_name)
    
    await green_api.download_file(file_url, file_path)
    
    caption = message_data.get("fileMessageData", {}).get("caption", "Пользователь прислал изображение.")
    
    structured_content = {
        "text": caption,
        "files": [file_path]
    }
    
    text_content = f"Пользователь прислал изображение. Подпись: {caption}"
    
    return text_content, structured_content, file_path


async def handle_button_response(message_data: dict) -> tuple[str, str | None]:
    """
    Handle interactive button response.
    Returns (button_text, button_id).
    """
    # Button responses come in messageData.buttonsResponseMessage
    button_data = message_data.get("buttonsResponseMessage", {})
    
    if not button_data:
        # Try alternative structure
        button_data = message_data.get("interactiveResponseMessage", {})
    
    button_text = button_data.get("selectedButtonText", "")
    button_id = button_data.get("selectedButtonId", "")
    
    logger.info(f"Button response: id={button_id}, text={button_text}")
    
    return button_text, button_id
