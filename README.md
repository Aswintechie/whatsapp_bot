<div align="center">

# 🤖 AswinBot — WhatsApp AI Assistant

**A smart, conversational AI chatbot for WhatsApp, powered by Claude AI**

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-3.x-black?logo=flask&logoColor=white)](https://flask.palletsprojects.com)
[![Claude AI](https://img.shields.io/badge/Claude-Haiku-orange?logo=anthropic&logoColor=white)](https://www.anthropic.com)
[![WhatsApp](https://img.shields.io/badge/WhatsApp-Business_API-25D366?logo=whatsapp&logoColor=white)](https://developers.facebook.com/docs/whatsapp)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

[Features](#-features) · [Tech Stack](#-tech-stack) · [Setup](#-setup) · [Configuration](#-configuration) · [Usage](#-usage) · [How It Works](#-how-it-works)

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
| 📋 **Message Logging** | Automatic per-user log files for all conversations |
| 🔒 **Webhook Verification** | Secure Meta webhook handshake with a verify token |
| 🌐 **REST Webhook** | Clean Flask endpoints for `GET` (verify) and `POST` (messages) |

---

## 🛠 Tech Stack

- **[Python 3.10+](https://python.org)** — Core language
- **[Flask](https://flask.palletsprojects.com)** — Lightweight web framework for the webhook server
- **[Anthropic SDK](https://github.com/anthropics/anthropic-sdk-python)** — Claude AI integration
- **[WhatsApp Business API](https://developers.facebook.com/docs/whatsapp)** — Meta's messaging platform
- **[python-dotenv](https://github.com/theskumar/python-dotenv)** — Environment variable management

---

## 📂 Project Structure

```
whatsapp_bot/
├── bot.py              # Main application — Flask app, webhook handler, Claude integration
├── system_prompt.txt   # Personality & rules for the AI assistant
├── requirements.txt    # Python dependencies
├── .gitignore
└── logs/               # Auto-created — per-user conversation logs
    └── <phone>.log
```

---

## 🚀 Setup

### 1. Prerequisites

- Python 3.10 or higher
- A [Meta Developer account](https://developers.facebook.com/) with a WhatsApp Business App
- An [Anthropic API key](https://console.anthropic.com/)
- A public HTTPS URL for your webhook (e.g. via [ngrok](https://ngrok.com) for local dev)

### 2. Clone the Repository

```bash
git clone https://github.com/Aswintechie/whatsapp_bot.git
cd whatsapp_bot
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables

Create a `.env` file in the project root:

```env
VERIFY_TOKEN=your_webhook_verify_token
ACCESS_TOKEN=your_whatsapp_access_token
PHONE_NUMBER_ID=your_phone_number_id
ANTHROPIC_API_KEY=your_anthropic_api_key

# Optional: enable per-user $10 spending cap
ENABLE_USER_BUDGET=false
```

### 5. Run the Bot

```bash
python bot.py
```

The server starts on `http://0.0.0.0:5000`. Expose it publicly (e.g. with ngrok) and register `https://<your-domain>/webhook` as your WhatsApp webhook URL.

---

## ⚙️ Configuration

| Variable | Required | Default | Description |
|---|---|---|---|
| `VERIFY_TOKEN` | ✅ | — | Secret token for WhatsApp webhook verification |
| `ACCESS_TOKEN` | ✅ | — | WhatsApp Business API access token |
| `PHONE_NUMBER_ID` | ✅ | — | Your WhatsApp Business phone number ID |
| `ANTHROPIC_API_KEY` | ✅ | — | API key from [console.anthropic.com](https://console.anthropic.com) |
| `ENABLE_USER_BUDGET` | ❌ | `false` | Set to `true` to limit each user to $10 of API usage |

---

## 💬 Usage

Once running, users can chat with the bot on WhatsApp using any of these built-in commands:

| Command | Response |
|---|---|
| `hi` / `hello` | Friendly greeting |
| `help` | Shows the help menu |
| `about` | Info about AswinBot and its creator |
| `reset` | Clears the conversation history |
| `bye` | Ends the chat gracefully |
| `thanks` / `thank you` | Polite acknowledgement |
| *anything else* | Sent to Claude AI for an intelligent reply |

---

## 🔍 How It Works

```
User sends WhatsApp message
        │
        ▼
  POST /webhook  (Flask)
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
5. **Logging & Budget** — Every message is appended to a per-user log file. If `ENABLE_USER_BUDGET=true`, the bot tracks token usage and stops responding once a user hits the $10 cap.

---

## 🙋 About the Creator

Built with ❤️ by **[Aswin](https://www.aswincloud.com)** — a software engineer from Pondicherry, India.  
Feel free to reach out or explore more of his projects at **[aswincloud.com](https://www.aswincloud.com)**.

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).
