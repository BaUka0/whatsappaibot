"""
Pytest configuration and fixtures for WhatsApp AI Bot tests.
"""
import pytest
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


@pytest.fixture
def mock_settings():
    """Mock settings for tests."""
    with patch('src.config.settings') as mock:
        mock.GREEN_API_INSTANCE_ID = 'test_instance'
        mock.GREEN_API_TOKEN = 'test_token'
        mock.GREEN_API_HOST = 'https://test.api.greenapi.com'
        mock.OPENROUTER_API_KEY = 'test_key'
        mock.OPENROUTER_MODEL = 'llama-3.1-8b-instant'
        mock.OPENROUTER_BASE_URL = 'https://test.api.com/openai/v1'
        mock.SYSTEM_PROMPT = 'You are a helpful assistant.'
        mock.BOT_NICKNAME = 'ботяра'
        mock.SUPABASE_URL = 'https://test.supabase.co'
        mock.SUPABASE_KEY = 'test_supabase_key'
        mock.MEDIA_DIR = '/tmp/media'
        yield mock


@pytest.fixture
def mock_supabase():
    """Mock Supabase client."""
    mock_client = MagicMock()
    mock_table = MagicMock()
    mock_client.table.return_value = mock_table
    
    # Mock chainable methods
    mock_table.select.return_value = mock_table
    mock_table.insert.return_value = mock_table
    mock_table.update.return_value = mock_table
    mock_table.upsert.return_value = mock_table
    mock_table.delete.return_value = mock_table
    mock_table.eq.return_value = mock_table
    mock_table.order.return_value = mock_table
    mock_table.limit.return_value = mock_table
    
    # Mock execute result
    mock_execute = MagicMock()
    mock_execute.data = []
    mock_table.execute.return_value = mock_execute
    
    with patch('supabase.create_client', return_value=mock_client):
        yield mock_client


@pytest.fixture
def mock_httpx():
    """Mock httpx client."""
    with patch('httpx.AsyncClient') as mock_client:
        mock_instance = AsyncMock()
        mock_client.return_value.__aenter__.return_value = mock_instance
        mock_client.return_value.__aexit__.return_value = None
        yield mock_instance


@pytest.fixture
def sample_message_data():
    """Sample incoming message data."""
    return {
        "typeWebhook": "incomingMessageReceived",
        "idMessage": "test_message_id",
        "senderData": {
            "chatId": "1234567890@c.us",
            "sender": "1234567890@c.us",
            "senderName": "Test User"
        },
        "messageData": {
            "typeMessage": "textMessage",
            "textMessageData": {
                "textMessage": "Hello, bot!"
            }
        }
    }


@pytest.fixture
def sample_group_message():
    """Sample group message data."""
    return {
        "typeWebhook": "incomingMessageReceived",
        "idMessage": "test_group_msg",
        "senderData": {
            "chatId": "1234567890@g.us",
            "sender": "9876543210@c.us",
            "senderName": "Group User"
        },
        "messageData": {
            "typeMessage": "textMessage",
            "textMessageData": {
                "textMessage": "ботяра привет"
            }
        }
    }
