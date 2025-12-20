"""
Structured logging configuration for the WhatsApp bot.
Provides JSON formatted logs for production use.
"""
import logging
import json
import sys
from datetime import datetime
from src.config import settings


class JSONFormatter(logging.Formatter):
    """Custom formatter that outputs logs as JSON."""
    
    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        
        # Add extra fields if present
        if hasattr(record, "chat_id"):
            log_data["chat_id"] = record.chat_id
        if hasattr(record, "sender_id"):
            log_data["sender_id"] = record.sender_id
        if hasattr(record, "message_type"):
            log_data["message_type"] = record.message_type
        if hasattr(record, "duration_ms"):
            log_data["duration_ms"] = record.duration_ms
            
        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
            
        return json.dumps(log_data, ensure_ascii=False)


class ContextAdapter(logging.LoggerAdapter):
    """Logger adapter that adds context to log messages."""
    
    def process(self, msg, kwargs):
        extra = kwargs.get("extra", {})
        extra.update(self.extra)
        kwargs["extra"] = extra
        return msg, kwargs


def setup_logging(json_format: bool = False):
    """
    Configure logging for the application.
    
    Args:
        json_format: If True, use JSON formatting (for production).
                    If False, use human-readable format (for development).
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(settings.LOG_LEVEL)
    
    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(settings.LOG_LEVEL)
    
    if json_format:
        console_handler.setFormatter(JSONFormatter())
    else:
        console_handler.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        ))
    
    root_logger.addHandler(console_handler)
    
    # Reduce noise from third-party libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)
    
    return root_logger


def get_logger(name: str, **extra) -> logging.LoggerAdapter:
    """
    Get a logger with optional context.
    
    Example:
        logger = get_logger(__name__, chat_id="123", sender_id="456")
        logger.info("Processing message")
    """
    logger = logging.getLogger(name)
    return ContextAdapter(logger, extra)
