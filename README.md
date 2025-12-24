# WhatsApp AI Bot 🤖

A production-ready WhatsApp bot written in Python (FastAPI + Celery + Redis).

## ✨ Features

- **🗣️ Text Chat** - Intelligent responses via Groq (Llama 3.3)
- **🎙️ Voice Messages** - Automatic transcription via Groq Whisper
- **🖼️ Image Understanding** - Vision support for image analysis  
- ** Chat Summary** - `/summary` command for group chats
- **🗄️ Supabase Backend** - Chat history and settings in PostgreSQL
- **⚡ Background Processing** - FastAPI BackgroundTasks (no Redis/Celery needed!)

## 🏗️ Architecture (Simplified)

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  Green API  │────▶│   FastAPI   │────▶│   Supabase  │
│  (WhatsApp) │     │   Standalone│     │  (DB/Auth)  │
└─────────────┘     └─────────────┘     └─────────────┘
```

## � Quick Start

1. **Configure Environment**
   ```bash
   cp .env.example .env
   # Edit .env: Add Green API, Groq, and Supabase credentials
   ```

2. **Run with Docker (Recommended)**
   ```bash
   docker-compose up -d --build
   ```

3. **Run Locally (Development)**
   ```bash
   pip install -r requirements.txt
   uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
   ```

## ⚙️ Configuration

```env
# Green API
GREEN_API_INSTANCE_ID=your_instance_id
GREEN_API_TOKEN=your_token

# Groq (LLM + STT)
OPENROUTER_API_KEY=gsk_your_groq_key
OPENROUTER_MODEL=llama-3.1-8b-instant
OPENROUTER_BASE_URL=https://api.groq.com/openai/v1

# Bot Settings
BOT_NICKNAME=ботяра
SUMMARY_MESSAGE_COUNT=50
```

## 💬 Commands

| Command | Description |
|---------|-------------|
| `/help` | Show available commands |
| `/reset` | Clear conversation history |
| `/summary` | Summarize last N messages (groups only) |
| `/ai on` | Enable auto-responses in group |
| `/ai off` | Disable auto-responses in group |

## 🔧 API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /` | Service info |
| `GET /health` | Health check (Redis status) |
| `POST /webhook` | Green API webhook |

## 📁 Project Structure

```
├── src/
│   ├── main.py           # FastAPI entrypoint
│   ├── worker.py         # Celery task processor (refactored)
│   ├── handlers.py       # Message type handlers
│   ├── config.py         # Settings
│   └── services/
│       ├── green_api.py  # WhatsApp API client
│       ├── llm.py        # LLM service (Groq)
│       ├── stt.py        # Speech-to-Text (Groq Whisper)
│       ├── context.py    # Conversation history (Redis)
│       ├── commands.py   # Bot commands registry
│       └── logging_config.py  # Structured logging
├── docker-compose.yml
├── Dockerfile
└── requirements.txt
```

## 🛡️ Security Features

- Rate limiting (30 req/min per chat)
- Message deduplication
- Webhook validation ready

## 📈 Monitoring

Health check endpoint: `GET /health`

```json
{
  "status": "healthy",
  "components": {
    "redis": "healthy",
    "api": "healthy"
  },
  "timestamp": 1703084400.123
}
```

## 📝 License

MIT
