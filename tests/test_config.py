"""
Tests for configuration settings.
"""
import os
import pytest
from unittest.mock import patch


def test_settings_load():
    """Test that settings load correctly from environment."""
    # Clear any existing env vars
    test_env = {
        'GREEN_API_INSTANCE_ID': 'test123',
        'GREEN_API_TOKEN': 'token123',
        'OPENROUTER_API_KEY': 'key123',
    }

    with patch.dict(os.environ, test_env, clear=True):
        from src.config import Settings
        settings = Settings()
        assert settings.GREEN_API_INSTANCE_ID == 'test123'
        assert settings.GREEN_API_TOKEN == 'token123'
        assert settings.OPENROUTER_API_KEY == 'key123'
        # Default value from config.py
        assert settings.BOT_NICKNAME is not None


def test_media_directory_creation():
    """Test that media directory is created on import."""
    # This is tested by the fact that import works without errors
    from src.config import settings
    assert os.path.exists(settings.MEDIA_DIR)
