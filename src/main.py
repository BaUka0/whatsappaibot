from fastapi import FastAPI, Request, HTTPException
from src.worker import process_message
from src.config import settings
from redis import asyncio as redis
import logging
import time

# Configure logging
logging.basicConfig(level=settings.LOG_LEVEL)
logger = logging.getLogger(__name__)

app = FastAPI(title=settings.APP_NAME)
redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)

# Rate limiting settings
RATE_LIMIT_WINDOW = 60  # seconds
RATE_LIMIT_MAX_REQUESTS = 30  # max requests per window per chat

@app.get("/")
async def root():
    return {"status": "ok", "service": settings.APP_NAME}

@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring."""
    try:
        # Check Redis connectivity
        await redis_client.ping()
        redis_status = "healthy"
    except Exception as e:
        redis_status = f"unhealthy: {str(e)}"
    
    return {
        "status": "healthy" if redis_status == "healthy" else "degraded",
        "components": {
            "redis": redis_status,
            "api": "healthy"
        },
        "timestamp": time.time()
    }

async def check_rate_limit(chat_id: str) -> bool:
    """Check if chat has exceeded rate limit. Returns True if allowed."""
    key = f"ratelimit:{chat_id}"
    current = await redis_client.get(key)
    
    if current is None:
        await redis_client.set(key, "1", ex=RATE_LIMIT_WINDOW)
        return True
    
    if int(current) >= RATE_LIMIT_MAX_REQUESTS:
        return False
    
    await redis_client.incr(key)
    return True

@app.post("/webhook")
async def webhook(request: Request):
    try:
        body = await request.json()
    except Exception:
        logger.error("Failed to parse JSON")
        return {"status": "error", "message": "Invalid JSON"}

    # Basic logging
    logger.info(f"Received webhook: {body}") 

    # Filter only incoming messages
    type_webhook = body.get("typeWebhook")
    if type_webhook != "incomingMessageReceived":
        return {"status": "ignored"}

    id_message = body.get("idMessage")
    if not id_message:
        return {"status": "ignored"}

    # Get chat ID for rate limiting
    sender_data = body.get("senderData", {})
    chat_id = sender_data.get("chatId", "unknown")

    # Rate limiting
    if not await check_rate_limit(chat_id):
        logger.warning(f"Rate limit exceeded for chat {chat_id}")
        return {"status": "rate_limited"}

    # Deduplication
    if await redis_client.get(f"dedup:{id_message}"):
        logger.info(f"Duplicate message {id_message} ignored")
        return {"status": "duplicate"}
    
    # Set dedup key for 10 minutes
    await redis_client.set(f"dedup:{id_message}", "1", ex=600)

    # Push to Celery
    process_message.delay(body)

    return {"status": "received"}
