from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from src.worker import process_message
from src.config import settings
from src.services.green_api import green_api
from src.services.llm import llm_service
from src.services.context import context_service
from src.services.supabase_db import supabase_db
import logging
import time

# Configure logging
logging.basicConfig(level=settings.LOG_LEVEL)
logger = logging.getLogger(__name__)

app = FastAPI(title=settings.APP_NAME)

@app.get("/")
async def root():
    return {"status": "ok", "service": settings.APP_NAME}

@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring."""
    components = {}
    overall_status = "healthy"

    # Check Supabase
    supabase_status = await supabase_db.health_check()
    components["supabase"] = supabase_status
    if not supabase_status["healthy"]:
        overall_status = "degraded"

    # Check Green API
    green_api_status = await green_api.health_check()
    components["green_api"] = green_api_status
    if not green_api_status["healthy"]:
        overall_status = "degraded"

    # Check Groq API
    groq_status = await llm_service.health_check()
    components["groq"] = groq_status
    if not groq_status["healthy"]:
        overall_status = "degraded"

    return {
        "status": overall_status,
        "components": components,
        "timestamp": time.time()
    }

@app.post("/webhook")
async def webhook(request: Request, background_tasks: BackgroundTasks):
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
    if not context_service.check_rate_limit(chat_id):
        logger.warning(f"Rate limit exceeded for chat {chat_id}")
        return {"status": "rate_limited"}

    # Deduplication
    if context_service.check_dedup(id_message):
        logger.info(f"Duplicate message {id_message} ignored")
        return {"status": "duplicate"}
    
    # Push to background processing
    background_tasks.add_task(process_message, body)

    return {"status": "received"}
