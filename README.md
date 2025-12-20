# WhatsApp AI Bot 🤖

A production-ready WhatsApp bot written in Python (FastAPI + Celery + Redis).

## ✨ Features

- **🗣️ Text Chat** - Intelligent responses via Groq (Llama 3.1, Gemma 2)
- **🎙️ Voice Messages** - Automatic transcription via Groq Whisper
- **🖼️ Image Understanding** - Vision support for image analysis  
- **💬 Quoted Messages** - Reply to voice messages to get transcription
- **📋 Chat Summary** - `/summary` command for group chat summarization
- **🧠 Context Awareness** - Remembers conversation history (Redis)
- **⚡ Rate Limiting** - Protection from spam
- **🔄 Transcription Caching** - Saves API calls

## 🏗️ Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  Green API  │────▶│   FastAPI   │────▶│   Celery    │
│  (WhatsApp) │     │   Webhook   │     │   Worker    │
└─────────────┘     └─────────────┘     └─────────────┘
                           │                   │
                           ▼                   ▼
                    ┌─────────────┐     ┌─────────────┐
                    │    Redis    │     │  Groq API   │
                    │   (Queue)   │     │  (LLM/STT)  │
                    └─────────────┘     └─────────────┘
```

## 📋 Prerequisites

1. **Green-API Instance**: [green-api.com](https://green-api.com)
2. **Groq API Key**: [console.groq.com](https://console.groq.com)
3. **Docker & Docker Compose**

## 🚀 Quick Start

```bash
# 1. Clone
git clone <repo_url>
cd whatsapp-ai-bot

# 2. Configure
cp .env.example .env
# Edit .env with your credentials

# 3. Run
docker-compose up -d --build

# 4. Set webhook in Green-API console
# URL: https://your-server.com/webhook
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
