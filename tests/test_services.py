"""
Tests for service layer.
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import httpx


@pytest.mark.asyncio
async def test_llm_service_get_response(mock_settings):
    """Test LLM service response."""
    from src.services.llm import LLMService

    with patch('src.services.llm.AsyncOpenAI') as mock_openai:
        mock_client = MagicMock()
        mock_openai.return_value = mock_client

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Test response"
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        llm = LLMService()
        messages = [{"role": "user", "content": "Hello"}]
        response = await llm.get_response(messages)

        assert response == "Test response"
        mock_client.chat.completions.create.assert_called_once()


@pytest.mark.asyncio
async def test_llm_service_health_check(mock_settings):
    """Test LLM service health check."""
    from src.services.llm import LLMService

    with patch('src.services.llm.fetch_available_models') as mock_fetch:
        mock_fetch.return_value = {"model1": "desc1", "model2": "desc2"}

        llm = LLMService()
        result = await llm.health_check()

        assert result["healthy"] is True
        assert "2 models available" in result["details"]


@pytest.mark.asyncio
async def test_llm_service_health_check_failure(mock_settings):
    """Test LLM service health check failure."""
    from src.services.llm import LLMService

    with patch('src.services.llm.fetch_available_models') as mock_fetch:
        mock_fetch.side_effect = Exception("API Error")

        llm = LLMService()
        result = await llm.health_check()

        assert result["healthy"] is False
        assert "API Error" in result["details"]


@pytest.mark.asyncio
async def test_green_api_send_message(mock_settings):
    """Test Green API send message."""
    from src.services.green_api import GreenAPIService

    with patch('httpx.AsyncClient') as mock_client:
        mock_instance = AsyncMock()
        mock_client.return_value.__aenter__.return_value = mock_instance
        mock_client.return_value.__aexit__.return_value = None

        mock_response = MagicMock()
        mock_response.json.return_value = {"idMessage": "sent_123"}
        mock_instance.post = AsyncMock(return_value=mock_response)

        api = GreenAPIService()
        result = await api.send_message("123@c.us", "Hello")

        assert result is not None
        mock_instance.post.assert_called_once()


@pytest.mark.asyncio
async def test_green_api_health_check(mock_settings):
    """Test Green API health check."""
    from src.services.green_api import GreenAPIService

    with patch('httpx.AsyncClient') as mock_client:
        mock_instance = AsyncMock()
        mock_client.return_value.__aenter__.return_value = mock_instance
        mock_client.return_value.__aexit__.return_value = None

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_instance.get = AsyncMock(return_value=mock_response)

        api = GreenAPIService()
        result = await api.health_check()

        assert result["healthy"] is True


@pytest.mark.asyncio
async def test_context_service(mock_supabase, mock_settings):
    """Test context service operations with Supabase."""
    from src.services.context import ContextService

    service = ContextService()

    # Test add_message
    await service.add_message("123@c.us", "user", "Hello")
    mock_supabase.table.assert_called_with("chat_messages")
    mock_supabase.table().insert.assert_called_once()

    # Test get_history
    mock_supabase.table().execute.return_value.data = [{"role": "user", "content": "Hello"}]
    history = await service.get_history("123@c.us")
    assert len(history) == 1
    assert history[0]["role"] == "user"

    # Test clear_history
    await service.clear_history("123@c.us")
    mock_supabase.table().delete.assert_called_once()


@pytest.mark.asyncio
async def test_stt_service(mock_settings):
    """Test STT service."""
    from src.services.stt import GroqSTT
    import tempfile
    import os

    # Create a temporary file for testing
    with tempfile.NamedTemporaryFile(suffix='.ogg', delete=False) as tmp:
        tmp.write(b"fake audio data")
        tmp_path = tmp.name

    try:
        with patch('src.services.stt.AsyncOpenAI') as mock_openai:
            mock_client = MagicMock()
            mock_openai.return_value = mock_client

            mock_transcription = MagicMock()
            mock_transcription.text = "Transcribed text"
            mock_client.audio.transcriptions.create = AsyncMock(return_value=mock_transcription)

            # Mock ffmpeg to avoid actual conversion
            with patch('src.services.stt._convert_to_mp3', return_value=tmp_path):
                stt = GroqSTT()
                result = await stt.transcribe(tmp_path)
                assert result == "Transcribed text"
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


@pytest.mark.asyncio
async def test_image_gen_enhance_prompt(mock_settings):
    """Test image generation prompt enhancement."""
    from src.services.image_gen import enhance_prompt
    from openai import AsyncOpenAI

    # Mock the AsyncOpenAI constructor
    with patch('openai.AsyncOpenAI') as mock_openai_class:
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Enhanced prompt"
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        result = await enhance_prompt("test prompt")
        assert result == "Enhanced prompt"


@pytest.mark.asyncio
async def test_search_duckduckgo(mock_settings):
    """Test DuckDuckGo search."""
    from src.services.search import search_duckduckgo

    with patch('httpx.AsyncClient') as mock_client:
        mock_instance = AsyncMock()
        mock_client.return_value.__aenter__.return_value = mock_instance
        mock_client.return_value.__aexit__.return_value = None

        mock_response = MagicMock()
        mock_response.text = '''
        <a rel="nofollow" class="result__a" href="https://example.com/page">Test Title</a>
        <a class="result__snippet">Test snippet</a>
        '''
        mock_instance.get = AsyncMock(return_value=mock_response)

        results = await search_duckduckgo("test query")
        assert len(results) > 0
        assert results[0]["title"] == "Test Title"
