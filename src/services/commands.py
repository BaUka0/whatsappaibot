"""
Bot commands handler module.
Centralizes all slash commands for better organization.
"""
from dataclasses import dataclass
from typing import Callable, Awaitable, Optional
import logging

logger = logging.getLogger(__name__)

@dataclass
class CommandResult:
    """Result of command execution."""
    handled: bool  # Whether the command was handled
    response: Optional[str] = None  # Response message to send
    stop_processing: bool = True  # Whether to stop further message processing

class CommandHandler:
    """Registry and handler for bot commands."""
    
    def __init__(self):
        self._commands: dict[str, Callable] = {}
        self._descriptions: dict[str, str] = {}
    
    def register(self, name: str, description: str = ""):
        """Decorator to register a command handler."""
        def decorator(func: Callable[..., Awaitable[CommandResult]]):
            self._commands[name.lower()] = func
            self._descriptions[name.lower()] = description
            return func
        return decorator
    
    def get_help_text(self) -> str:
        """Generate help text from registered commands."""
        lines = ["Команды:"]
        for name, desc in sorted(self._descriptions.items()):
            if desc:
                lines.append(f"/{name} - {desc}")
            else:
                lines.append(f"/{name}")
        return "\n".join(lines)
    
    async def handle(self, text: str, **context) -> CommandResult:
        """
        Try to handle text as a command.
        Returns CommandResult indicating if command was handled.
        """
        text = text.strip()
        
        # Check if it's a command (starts with /)
        if not text.startswith("/"):
            return CommandResult(handled=False)
        
        # Parse command and args
        parts = text[1:].split(maxsplit=1)
        cmd_name = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""
        
        # Find handler
        handler = self._commands.get(cmd_name)
        if not handler:
            return CommandResult(handled=False)
        
        try:
            result = await handler(args=args, **context)
            return result
        except Exception as e:
            logger.error(f"Command {cmd_name} failed: {e}")
            return CommandResult(
                handled=True,
                response=f"Ошибка выполнения команды: {str(e)}"
            )

# Global command handler instance
commands = CommandHandler()
