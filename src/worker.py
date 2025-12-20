"""
Celery worker for processing WhatsApp messages.
Refactored for better organization with handlers in separate module.
"""
from celery import Celery
import asyncio
import logging
import re
import os
from src.config import settings
from src.services.green_api import green_api
from src.services.llm import llm_service
from src.services.stt import get_stt_provider
from src.services.context import context_service
from src.handlers import (
    handle_text_message,
    handle_extended_text_message,
    handle_quoted_message,
    handle_audio_message,
    handle_image_message,
    handle_button_response,
)

# Celery setup
celery_app = Celery(
    "whatsapp_bot",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND
)

logging.basicConfig(level=settings.LOG_LEVEL)
logger = logging.getLogger(__name__)


@celery_app.task
def process_message(event_data: dict):
    """Process incoming webhook event."""
    try:
        asyncio.run(_process_message_async(event_data))
    except Exception as e:
        logger.error(f"Task Failed: {e}")


async def _process_message_async(event_data: dict):
    """Main message processing logic."""
    logger.info(f"Processing event: {event_data}")
    
    # Validate event type
    if event_data.get("typeWebhook") != "incomingMessageReceived":
        return
    
    # Extract sender info
    sender_data = event_data.get("senderData", {})
    chat_id = sender_data.get("chatId")
    sender_id = sender_data.get("sender", chat_id)
    sender_name = sender_data.get("senderName", "User")
    message_data = event_data.get("messageData", {})
    message_type = message_data.get("typeMessage")
    
    # Check blacklist
    if await context_service.is_blacklisted(sender_id):
        logger.info(f"Blocked message from blacklisted user: {sender_id}")
        return
    
    # Process message by type
    text_content = ""
    quoted_context = None
    structured_content = None
    file_path = None
    has_media = False
    
    if message_type == "textMessage":
        text_content, _ = await handle_text_message(message_data)
        
    elif message_type == "extendedTextMessage":
        text_content, quoted_context = await handle_extended_text_message(message_data, chat_id)
        
    elif message_type == "quotedMessage":
        text_content, quoted_context = await handle_quoted_message(message_data, chat_id)
        
    elif message_type in ["audioMessage", "voiceMessage"]:
        text_content, should_skip = await handle_audio_message(message_data, chat_id)
        if should_skip:
            return
            
    elif message_type == "imageMessage":
        text_content, structured_content, file_path = await handle_image_message(message_data, chat_id)
        has_media = structured_content is not None
    
    elif message_type == "buttonsResponseMessage":
        # Handle button clicks
        button_text, button_id = await handle_button_response(message_data)
        if button_id:
            # Process button action based on ID
            await _handle_button_action(chat_id, button_id, button_text)
            return
    
    if not text_content:
        return
    
    # Check if group chat
    is_group = chat_id.endswith("@g.us")
    
    # Handle commands
    command_result = await _handle_commands(
        text_content, chat_id, sender_id, is_group
    )
    if command_result:
        return
    
    # Store group message for summarization
    if is_group:
        content_to_store = text_content
        if message_type in ["audioMessage", "voiceMessage"] and "Текст:" in text_content:
            content_to_store = text_content.split("Текст:")[-1].strip()
        await context_service.add_group_message(chat_id, sender_name, content_to_store)
    
    # Check if should reply in group
    if is_group and not await _should_reply_in_group(chat_id, text_content):
        return
    
    # Prepare LLM request
    history = await context_service.get_history(chat_id)
    llm_messages = [{"role": msg["role"], "content": msg["content"]} for msg in history]
    
    current_content = structured_content if has_media else text_content
    
    # Add quoted context if present
    if quoted_context:
        if isinstance(current_content, str):
            current_content = f"{quoted_context}\n\nВопрос пользователя: {current_content}"
        elif isinstance(current_content, dict):
            current_content["text"] = f"{quoted_context}\n\nВопрос пользователя: {current_content.get('text', '')}"
    
    llm_messages.append({"role": "user", "content": current_content})
    
    # Get chat-specific model or use default
    chat_model = await context_service.get_model(chat_id)
    
    # Get LLM response
    response_text = await llm_service.get_response(llm_messages, model=chat_model)
    
    # Update history
    await context_service.add_message(chat_id, "user", text_content)
    await context_service.add_message(chat_id, "assistant", response_text)
    
    # Send response
    await green_api.send_message(chat_id, response_text)
    
    # Cleanup media
    if has_media and file_path and os.path.exists(file_path):
        os.remove(file_path)


async def _should_reply_in_group(chat_id: str, text: str) -> bool:
    """Check if bot should reply in group chat."""
    is_enabled = await context_service.is_ai_enabled(chat_id)
    
    msg_lower = text.lower()
    bot_nickname = settings.BOT_NICKNAME.lower()
    
    # Match exact word
    pattern = rf'\b{re.escape(bot_nickname)}\b'
    is_triggered = bool(re.search(pattern, msg_lower))
    
    # Check if message starts with nickname
    if not is_triggered:
        is_triggered = msg_lower.startswith(f"{bot_nickname} ") or msg_lower.startswith(f"{bot_nickname},")
    
    return is_enabled or is_triggered


async def _handle_button_action(chat_id: str, button_id: str, button_text: str):
    """
    Handle interactive button action based on button ID.
    Add custom button handlers here.
    """
    # Built-in button actions
    if button_id == "btn_reset":
        await context_service.clear_history(chat_id)
        await green_api.send_message(chat_id, "🔄 Память сброшена!")
        return
    
    elif button_id == "btn_help":
        await _send_help_with_buttons(chat_id)
        return
    
    elif button_id == "btn_transcribe":
        current = await context_service.get_transcribe_mode(chat_id)
        await context_service.set_transcribe_mode(chat_id, not current)
        msg = "🎙️ Транскрибация ВКЛ" if not current else "🤖 Транскрибация ВЫКЛ"
        await green_api.send_message(chat_id, msg)
        return
    
    elif button_id == "btn_ai_on":
        await context_service.set_ai_enabled(chat_id, True)
        await green_api.send_message(chat_id, "🤖 AI включен")
        return
    
    elif button_id == "btn_ai_off":
        await context_service.set_ai_enabled(chat_id, False)
        await green_api.send_message(chat_id, "😴 AI выключен")
        return
    
    # Custom button: treat as message
    logger.info(f"Unknown button action: {button_id}")
    # Could process button_text as a message here if needed


async def _handle_commands(text: str, chat_id: str, sender_id: str, is_group: bool) -> bool:
    """
    Handle slash commands.
    Returns True if command was handled and processing should stop.
    """
    cmd = text.strip().lower()
    
    # /ai on|off
    if cmd == "/ai on":
        await context_service.set_ai_enabled(chat_id, True)
        await green_api.send_message(chat_id, "🤖 Автоответы включены.")
        return True
    elif cmd == "/ai off":
        await context_service.set_ai_enabled(chat_id, False)
        await green_api.send_message(chat_id, "😴 Автоответы выключены.")
        return True
    
    # /reset
    if cmd == "/reset":
        await context_service.clear_history(chat_id)
        await context_service.clear_group_messages(chat_id)
        await green_api.send_message(chat_id, "🔄 Контекст сброшен.")
        return True
    
    # /help
    if cmd == "/help":
        help_text = f"""📚 *Команды бота:*

🔄 /reset - сбросить память
🤖 /ai on|off - автоответы в группе
📋 /summary - резюме чата
🎙️ /transcribe - транскрибация
📊 /stats - статистика
🔧 /model - сменить AI модель
🔍 /search - поиск с AI-ответом
🎨 /draw - генерация картинок

💡 Ник: *{settings.BOT_NICKNAME}*"""
        await green_api.send_message(chat_id, help_text)
        return True
    
    # /transcribe
    if cmd == "/transcribe":
        current = await context_service.get_transcribe_mode(chat_id)
        await context_service.set_transcribe_mode(chat_id, not current)
        msg = "🎙️ Режим транскрибации ВКЛ" if not current else "🤖 Режим транскрибации ВЫКЛ"
        await green_api.send_message(chat_id, msg)
        return True
    
    # /stats
    if cmd == "/stats":
        history = await context_service.get_history(chat_id)
        # Get current model for this chat
        current_model = await context_service.get_model(chat_id) or settings.OPENROUTER_MODEL
        stats = f"""📊 *Статистика:*

💬 Сообщений в памяти: {len(history)}
🔧 Модель: {current_model}
🤖 Ник: {settings.BOT_NICKNAME}

Смена модели: /model"""
        await green_api.send_message(chat_id, stats)
        return True
    
    # /model - view or change model
    if cmd == "/model" or cmd.startswith("/model "):
        # Fetch models dynamically from Groq API
        available_models = await llm_service.get_available_models()
        
        parts = text.strip().split(maxsplit=1)
        current_model = await context_service.get_model(chat_id) or settings.OPENROUTER_MODEL
        
        if len(parts) == 1:
            # Show available models
            lines = [f"🔧 *Доступные модели ({len(available_models)}):*\n"]
            for model_id, desc in sorted(available_models.items()):
                marker = "✅" if model_id == current_model else "•"
                lines.append(f"{marker} `{model_id}`\n   {desc}")
            lines.append(f"\n💡 Смена: /model <название>")
            await green_api.send_message(chat_id, "\n".join(lines))
        else:
            # Set model
            new_model = parts[1].strip()
            if new_model in available_models:
                await context_service.set_model(chat_id, new_model)
                await green_api.send_message(
                    chat_id, 
                    f"✅ Модель изменена на:\n`{new_model}`\n{available_models[new_model]}"
                )
            else:
                await green_api.send_message(
                    chat_id, 
                    f"❌ Модель `{new_model}` не найдена.\nНапиши /model для списка."
                )
        return True
    
    # /search - web search with AI summarization (Perplexity-style)
    if cmd.startswith("/search ") or cmd == "/search":
        parts = text.strip().split(maxsplit=1)
        if len(parts) < 2:
            await green_api.send_message(
                chat_id, 
                "🔍 *Поиск в интернете*\n\n"
                "Использование: /search <запрос>\n"
                "Пример: /search погода Алматы\n\n"
                "💡 AI проанализирует результаты и даст ответ с источниками"
            )
            return True
        
        query = parts[1]
        await green_api.send_message(chat_id, f"🔍 Ищу: _{query}_\n⏳ Анализирую источники...")
        
        from src.services.search import search_and_summarize
        # Use chat's selected model
        chat_model = await context_service.get_model(chat_id)
        result = await search_and_summarize(query, model=chat_model)
        await green_api.send_message(chat_id, result)
        return True
    
    # /draw - image generation with Pollinations.ai
    if cmd.startswith("/draw ") or cmd == "/draw":
        parts = text.strip().split(maxsplit=1)
        if len(parts) < 2:
            await green_api.send_message(chat_id, "🎨 *Генерация изображений*\n\nИспользование: /draw <описание>\nПример: /draw кот в космосе\n\n💡 Промпт автоматически улучшается AI")
            return True
        
        prompt = parts[1]
        await green_api.send_message(chat_id, f"🎨 Генерирую: _{prompt}_\n⏳ Улучшаю промпт и создаю изображение...")
        
        from src.services.image_gen import generate_image
        
        # Generate image with prompt enhancement, using chat's selected model
        chat_model = await context_service.get_model(chat_id)
        file_path, enhanced_prompt, seed = await generate_image(prompt, llm_model=chat_model)
        
        if file_path and os.path.exists(file_path):
            # Create caption with original and enhanced prompt
            prompt_preview = enhanced_prompt[:150] + '...' if len(enhanced_prompt) > 150 else enhanced_prompt
            caption = f"🎨 *{prompt}*\n\n✨ _{prompt_preview}_"
            if seed:
                caption += f"\n\n🌱 Seed: {seed}"
            
            # Upload to WhatsApp using SendFileByUpload
            result = await green_api.send_file_by_upload(
                chat_id=chat_id,
                file_path=file_path,
                caption=caption,
                file_name=f"art_{seed}.png"
            )
            
            # Cleanup local file
            try:
                os.remove(file_path)
                logger.info(f"Cleaned up: {file_path}")
            except Exception as e:
                logger.warning(f"Failed to cleanup: {e}")
            
            if not result:
                await green_api.send_message(chat_id, "❌ Не удалось отправить картинку. Попробуйте ещё раз.")
        else:
            await green_api.send_message(chat_id, "❌ Ошибка генерации.\n\n💡 Попробуйте:\n• Другой промпт\n• Более простое описание\n• Английский язык")
        
        return True
    
    # /summary (groups only)
    if cmd == "/summary":
        if not is_group:
            await green_api.send_message(chat_id, "Команда доступна только в группах.")
            return True
        await _handle_summary_command(chat_id)
        return True
    
    # Admin commands
    if settings.ADMIN_CHAT_ID and sender_id == settings.ADMIN_CHAT_ID:
        if text.strip().startswith("/ban "):
            target = text.strip()[5:].strip()
            if target:
                await context_service.add_to_blacklist(target)
                await green_api.send_message(chat_id, f"🚫 {target} заблокирован")
            return True
        
        if text.strip().startswith("/unban "):
            target = text.strip()[7:].strip()
            if target:
                await context_service.remove_from_blacklist(target)
                await green_api.send_message(chat_id, f"✅ {target} разблокирован")
            return True
        
        if cmd == "/blacklist":
            bl = await context_service.get_blacklist()
            if bl:
                await green_api.send_message(chat_id, "🚫 Blacklist:\n" + "\n".join(f"• {u}" for u in bl))
            else:
                await green_api.send_message(chat_id, "Blacklist пуст")
            return True
    
    return False


async def _handle_summary_command(chat_id: str):
    """Handle /summary command for group chats."""
    await green_api.send_message(chat_id, "⏳ Собираю сообщения...")
    
    raw_messages = await green_api.get_chat_history(chat_id, settings.SUMMARY_MESSAGE_COUNT)
    if not raw_messages:
        await green_api.send_message(chat_id, "Нет сообщений для суммаризации.")
        return
    
    formatted_messages = []
    stt = get_stt_provider()
    audio_count = 0
    
    for msg in reversed(raw_messages):
        msg_type = msg.get("typeMessage", "")
        sender = msg.get("senderName", "?")
        if msg.get("type") == "outgoing":
            sender = "Бот"
        
        content = None
        
        if msg_type == "textMessage":
            content = msg.get("textMessage", "")
        elif msg_type == "extendedTextMessage":
            content = msg.get("extendedTextMessage", {}).get("text", "")
        elif msg_type in ["audioMessage", "voiceMessage"]:
            download_url = msg.get("downloadUrl", "")
            if download_url:
                try:
                    file_path = os.path.join(settings.MEDIA_DIR, f"sum_{msg.get('idMessage', 'tmp')}.ogg")
                    await green_api.download_file(download_url, file_path)
                    transcription = await stt.transcribe(file_path)
                    if os.path.exists(file_path):
                        os.remove(file_path)
                    if transcription:
                        content = f"[🎙️]: {transcription}"
                        audio_count += 1
                except Exception as e:
                    logger.error(f"Summary audio transcription failed: {e}")
                    content = "[🎙️]"
            else:
                content = "[🎙️]"
        elif msg_type == "imageMessage":
            content = f"[📷] {msg.get('caption', '')}"
        
        if content:
            formatted_messages.append(f"{sender}: {content}")
    
    if not formatted_messages:
        await green_api.send_message(chat_id, "Нет сообщений для суммаризации.")
        return
    
    # Limit total text to avoid token limit issues
    # ~4 chars per token, Groq limit is 6000 tokens, we want ~4000 chars max for content
    MAX_CONTENT_CHARS = 4000
    messages_text = "\n".join(formatted_messages)
    if len(messages_text) > MAX_CONTENT_CHARS:
        # Truncate from the beginning (keep recent messages)
        messages_text = "...[обрезано]...\n" + messages_text[-MAX_CONTENT_CHARS:]
    
    # Get chat-specific model
    chat_model = await context_service.get_model(chat_id)
    
    prompt = f"{settings.SUMMARY_PROMPT}\n\n--- История ---\n{messages_text}"
    summary = await llm_service.get_response([{"role": "user", "content": prompt}], model=chat_model)
    
    note = f" (🎙️ {audio_count})" if audio_count else ""
    await green_api.send_message(chat_id, f"📋 *Резюме* ({len(formatted_messages)} сообщений{note}):\n\n{summary}")
