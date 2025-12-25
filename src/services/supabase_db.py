import logging
from supabase import create_client, Client
from src.config import settings

logger = logging.getLogger(__name__)

class SupabaseService:
    def __init__(self):
        self.url = settings.SUPABASE_URL
        self.key = settings.SUPABASE_KEY
        self.client: Client = create_client(self.url, self.key)

    async def health_check(self) -> dict:
        """Check Supabase connectivity."""
        try:
            # Try to list tables or perform a simple query
            # Run in thread pool as client.table()...execute() is blocking
            import asyncio
            loop = asyncio.get_running_loop()
            
            def _check():
                return self.client.table("chat_messages").select("count", count="exact").limit(1).execute()
                
            await loop.run_in_executor(None, _check)
            return {"healthy": True, "details": "Connected to Supabase"}
        except Exception as e:
            logger.error(f"Supabase health check failed: {e}")
            return {"healthy": False, "details": str(e)}

    def get_client(self) -> Client:
        return self.client

supabase_db = SupabaseService()
