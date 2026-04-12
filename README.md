<div align="center">

# 🤖 AswinBot — WhatsApp AI Assistant

**A smart, conversational AI chatbot for WhatsApp, powered by Claude AI**

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-3.x-black?logo=flask&logoColor=white)](https://flask.palletsprojects.com)
[![Claude AI](https://img.shields.io/badge/Claude-Haiku-orange?logo=anthropic&logoColor=white)](https://www.anthropic.com)
[![WhatsApp](https://img.shields.io/badge/WhatsApp-Business_API-25D366?logo=whatsapp&logoColor=white)](https://developers.facebook.com/docs/whatsapp)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

[Features](#-features) · [Tech Stack](#-tech-stack) · [Setup](#-setup) · [Docker](#-docker) · [Configuration](#-configuration) · [Usage](#-usage) · [How It Works](#-how-it-works)

</div>

---

## 📌 Overview

**AswinBot** is a fully-featured WhatsApp chatbot that brings the power of Anthropic's Claude AI directly into your WhatsApp conversations. Built with Python and Flask, it handles incoming messages via the WhatsApp Business API, maintains per-user conversation history, and supports optional usage budgets — making it production-ready right out of the box.

---

## ✨ Features

| Feature | Description |
|---|---|
| 🧠 **AI-Powered Replies** | Leverages Claude Haiku for natural, intelligent responses |
| 💬 **Conversation Memory** | Maintains up to 20 messages of context per user |
| ⚡ **Quick Replies** | Instant responses for common keywords (`hi`, `help`, `about`, `bye`, etc.) |
| 🔄 **Conversation Reset** | Users can type `reset` to start a fresh session |
| 💰 **Budget Control** | Optional per-user spending cap (default: $10 USD) |
| 🔒 **Webhook Verification** | Secure Meta webhook handshake with a verify token |
| 🌐 **REST Webhook** | Clean Flask endpoints for `GET` (verify) and `POST` (messages) |
| 🐳 **Docker Ready** | Single-command deployment with Gunicorn WSGI server |

---

## 🛠 Tech Stack

- **[Python 3.10+](https://python.org)** — Core language
- **[Flask](https://flask.palletsprojects.com)** + **[Gunicorn](https://gunicorn.org)** — Web framework + production WSGI server
- **[Anthropic SDK](https://github.com/anthropics/anthropic-sdk-python)** — Claude AI integration
- **[WhatsApp Business API](https://developers.facebook.com/docs/whatsapp)** — Meta's messaging platform
- **[python-dotenv](https://github.com/theskumar/python-dotenv)** — Environment variable management

---

## 📂 Project Structure

```
whatsapp_bot/
├── bot.py              # Main application — Flask app, webhook handler, Claude integration
├── system_prompt.txt   # (gitignored) Personality & rules for the AI — create from example
├── system_prompt.txt.example  # Template for the system prompt
├── .env.example        # Template for environment variables
├── requirements.txt    # Python dependencies
├── Dockerfile          # Container build
└── LICENSE
```

---

## 🚀 Setup

### 1. Prerequisites

- Python 3.10 or higher (or Docker)
- A [Meta Developer account](https://developers.facebook.com/) with a WhatsApp Business App
- An [Anthropic API key](https://console.anthropic.com/)
- A public HTTPS URL for your webhook (see [Cloudflare Tunnel](#exposing-locally-with-cloudflare-tunnel) below)

### 2. Clone & Install

```bash
git clone https://github.com/Aswintechie/whatsapp_bot.git
cd whatsapp_bot
pip install -r requirements.txt
```

### 3. Configure Environment Variables

```bash
cp .env.example .env
# Edit .env and fill in your values
```

### 4. Add Your System Prompt

```bash
cp system_prompt.txt.example system_prompt.txt
# Edit system_prompt.txt to define the bot's personality and rules
```

### 5. Run the Bot

**Development:**
```bash
python bot.py
```

**Production (recommended):**
```bash
gunicorn --bind 0.0.0.0:5000 --workers 2 --timeout 60 bot:app
```

---

## 🐳 Docker

```bash
# Build
docker build -t aswinbot .

# Run
docker run -d --env-file .env \
  -v $(pwd)/system_prompt.txt:/app/system_prompt.txt:ro \
  -p 5000:5000 aswinbot
```

---

## 🌐 Exposing Locally with Cloudflare Tunnel

1. Install `cloudflared`:
   ```bash
   # macOS
   brew install cloudflare/cloudflare/cloudflared

   # Linux
   curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -o cloudflared
   chmod +x cloudflared && sudo mv cloudflared /usr/local/bin/
   ```

2. Start a quick tunnel (no account needed):
   ```bash
   cloudflared tunnel --url http://localhost:5000
   ```

3. Copy the generated `https://<random>.trycloudflare.com` URL and register:
   ```
   https://<random>.trycloudflare.com/webhook
   ```

> For a stable permanent URL, [create a named tunnel](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/get-started/) with a free Cloudflare account.

---

## ⚙️ Configuration

| Variable | Required | Default | Description |
|---|---|---|---|
| `VERIFY_TOKEN` | ✅ | — | Secret token for WhatsApp webhook verification |
| `ACCESS_TOKEN` | ✅ | — | WhatsApp Business API access token |
| `PHONE_NUMBER_ID` | ✅ | — | Your WhatsApp Business phone number ID |
| `ANTHROPIC_API_KEY` | ✅ | — | API key from [console.anthropic.com](https://console.anthropic.com) |
| `ADMIN_NUMBER` | ✅ | — | Phone number (no `+`) allowed to run admin `/commands` |
| `ENABLE_USER_BUDGET` | ❌ | `false` | Set to `true` to limit each user to $10 of API usage |
| `SYSTEM_PROMPT` | ❌ | — | Inline system prompt (fallback if `system_prompt.txt` is absent) |

See `.env.example` for a full template.

---

## 💬 Usage

Once running, users can chat with the bot on WhatsApp:

| Command | Response |
|---|---|
| `hi` / `hello` | Friendly greeting |
| `help` | Shows the help menu |
| `about` | Info about AswinBot and its creator |
| `reset` | Clears the conversation history |
| `bye` | Ends the chat gracefully |
| `thanks` / `thank you` | Polite acknowledgement |
| *anything else* | Sent to Claude AI for an intelligent reply |

### Admin Commands (ADMIN_NUMBER only)

| Command | Description |
|---|---|
| `/help` | Show admin command list |
| `/stats` | Show per-user token usage and cost |
| `/clearall` | Clear all conversation histories |
| `/addrule <text>` | Append a rule to `system_prompt.txt` |
| `/setbudget <amount>` | Change per-user USD budget |
| `/reboot` | Restart the bot process |

---

## 🔍 How It Works

```
User sends WhatsApp message
        │
        ▼
  POST /webhook  (Flask + Gunicorn)
        │
        ├──► Admin command? ──► Execute and reply
        │
        ├──► Keyword match? ──► Send quick reply
        │
        └──► Call Claude API (with conversation history)
                    │
                    ▼
              Send AI reply back via
           WhatsApp Business API
```

1. **Webhook Verification** — Meta sends a `GET /webhook` request with a challenge token; the bot responds with the challenge if the verify token matches.
2. **Message Routing** — Incoming `POST /webhook` payloads are parsed to extract the sender and message text.
3. **Quick Replies** — If the message matches a known keyword, a pre-defined response is returned instantly.
4. **AI Responses** — All other messages are forwarded to Claude Haiku with the full conversation history (up to the last 20 turns) and the configured system prompt.
5. **Budget** — If `ENABLE_USER_BUDGET=true`, the bot tracks token usage per user and stops responding once they hit the $10 cap.

---

## 🙋 About the Creator

Built with ❤️ by **[Aswin](https://www.aswincloud.com)** — a software engineer from Pondicherry, India.  
Feel free to reach out or explore more of his projects at **[aswincloud.com](https://www.aswincloud.com)**.

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).
