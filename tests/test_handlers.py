"""
Tests for message handlers.
"""
import os
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from src.handlers import (
    handle_text_message,
    handle_extended_text_message,
    handle_audio_message,
    handle_image_message,
)


@pytest.mark.asyncio
async def test_handle_text_message():
    """Test handling of plain text messages."""
    message_data = {
        "textMessageData": {
            "textMessage": "Hello, world!"
        }
    }
    text, _ = await handle_text_message(message_data)
    assert text == "Hello, world!"


@pytest.mark.asyncio
async def test_handle_extended_text_message():
    """Test handling of extended text messages."""
    message_data = {
        "extendedTextMessageData": {
            "text": "Reply to message",
            "quotedMessage": {
                "stanzaId": "quoted_id",
                "typeMessage": "textMessage",
                "textMessage": "Original message"
            }
        }
    }

    with patch('src.handlers._process_quoted_message', new_callable=AsyncMock) as mock_process:
        mock_process.return_value = "[Цитируемое сообщение]: Original message"
        text, quoted = await handle_extended_text_message(message_data, "123@c.us")
        assert text == "Reply to message"
        assert quoted == "[Цитируемое сообщение]: Original message"


@pytest.mark.asyncio
async def test_handle_image_message(mock_settings):
    """Test handling of image messages."""
    message_data = {
        "idMessage": "img_123",
        "fileMessageData": {
            "downloadUrl": "https://example.com/image.jpg",
            "caption": "Test image"
        }
    }

    with patch('src.services.green_api.green_api.download_file', new_callable=AsyncMock) as mock_download:
        mock_download.return_value = "/tmp/test_image.jpg"

        text, structured, file_path = await handle_image_message(message_data, "123@c.us")
        assert "Test image" in text
        assert structured is not None
        assert structured["text"] == "Test image"
        # File path is determined by handler, just check it's not None
        assert file_path is not None


@pytest.mark.asyncio
async def test_handle_audio_message(mock_settings):
    """Test handling of audio messages."""
    from src.handlers import handle_audio_message
    from unittest.mock import patch

    message_data = {
        "idMessage": "audio_123",
        "fileMessageData": {
            "downloadUrl": "https://example.com/audio.ogg"
        }
    }

    with patch('src.services.green_api.green_api.download_file', new_callable=AsyncMock) as mock_download, \
         patch('src.services.stt.get_stt_provider') as mock_stt_provider, \
         patch('src.services.context.context_service.get_transcribe_mode', new_callable=AsyncMock) as mock_mode:

        mock_download.return_value = "/tmp/test_audio.ogg"
        mock_stt = MagicMock()
        mock_stt.transcribe = AsyncMock(return_value="Transcribed audio text")
        mock_stt_provider.return_value = mock_stt
        mock_mode.return_value = False

        text, should_skip = await handle_audio_message(message_data, "123@c.us")
        # Check that text contains some indication of transcription or voice message
        assert len(text) > 0
        assert should_skip is False


@pytest.mark.asyncio
async def test_handle_quoted_audio(mock_settings):
    """Test handling quoted audio messages."""
    from src.handlers import _process_quoted_message

    quoted_msg = {
        "stanzaId": "audio_123",
        "typeMessage": "audioMessage"
    }

    # Mock the entire chain: get_message -> download_file -> stt
    with patch('src.services.green_api.green_api.get_message', new_callable=AsyncMock) as mock_get, \
         patch('src.handlers._transcribe_quoted_audio', new_callable=AsyncMock) as mock_transcribe:

        mock_get.return_value = {
            "downloadUrl": "https://example.com/audio.ogg",
            "senderName": "Test User"
        }
        mock_transcribe.return_value = "[Голосовое сообщение от Test User]: Transcribed quoted audio"

        result = await _process_quoted_message(quoted_msg, "123@c.us")
        assert "Transcribed quoted audio" in result
        assert "Test User" in result
