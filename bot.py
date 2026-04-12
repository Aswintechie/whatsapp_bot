import os
import re
import sys
import json
import traceback
import threading
from pathlib import Path
from collections import defaultdict

import requests
from flask import Flask, request
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

REQUIRED_ENV_VARS = ["VERIFY_TOKEN", "ACCESS_TOKEN", "PHONE_NUMBER_ID", "ANTHROPIC_API_KEY"]
missing = [v for v in REQUIRED_ENV_VARS if not os.getenv(v)]
if missing:
    sys.exit(f"Missing required env vars: {', '.join(missing)}")

VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
ADMIN_NUMBER = os.getenv("ADMIN_NUMBER", "916380157944")

MAX_HISTORY = 20

client = Anthropic(api_key=ANTHROPIC_API_KEY)
app = Flask(__name__)

SCRIPT_DIR = Path(__file__).resolve().parent

def load_system_prompt():
    with open(SCRIPT_DIR / "system_prompt.txt", "r") as f:
        return f.read()

SYSTEM_PROMPT = load_system_prompt()

USAGE_FILE = SCRIPT_DIR / "usage.json"
CONFIG_FILE = SCRIPT_DIR / "bot_config.json"
ENABLE_USER_BUDGET = os.getenv("ENABLE_USER_BUDGET", "false").lower() == "true"

INPUT_COST_PER_TOKEN  = 0.80 / 1_000_000
OUTPUT_COST_PER_TOKEN = 4.00 / 1_000_000

_usage_lock = threading.Lock()


def load_config() -> dict:
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    return {}


def save_config(cfg: dict):
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2)


USER_BUDGET = load_config().get("user_budget", 10.0)


def load_usage() -> dict:
    if USAGE_FILE.exists():
        with open(USAGE_FILE, "r") as f:
            return json.load(f)
    return {}


def save_usage(usage: dict):
    with open(USAGE_FILE, "w") as f:
        json.dump(usage, f, indent=2)


def get_user_cost(sender: str) -> float:
    with _usage_lock:
        usage = load_usage()
    u = usage.get(sender, {})
    return (u.get("input_tokens", 0) * INPUT_COST_PER_TOKEN
            + u.get("output_tokens", 0) * OUTPUT_COST_PER_TOKEN)


def record_usage(sender: str, input_tokens: int, output_tokens: int):
    with _usage_lock:
        usage = load_usage()
        u = usage.setdefault(sender, {"input_tokens": 0, "output_tokens": 0})
        u["input_tokens"]  += input_tokens
        u["output_tokens"] += output_tokens
        save_usage(usage)


conversation_history: dict[str, list[dict]] = defaultdict(list)
_reboot_pending = False

QUICK_REPLIES = {
    "hi": (
        "Hey there! 👋 I'm AswinBot, your WhatsApp AI assistant.\n"
        "Ask me anything or type *help* to see what I can do!"
    ),
    "hello": (
        "Hello! 😊 Welcome to AswinBot.\n"
        "I'm here to help — just type your question or send *help* for options."
    ),
    "welcome": (
        "Welcome to AswinBot! 🎉\n\n"
        "I'm an AI assistant built by Aswin. I can help you with:\n"
        "• Answering questions\n"
        "• Giving recommendations\n"
        "• Brainstorming ideas\n"
        "• Having a friendly chat\n\n"
        "Just type anything to get started!"
    ),
    "help": (
        "📖 *AswinBot Help*\n\n"
        "Here's what you can do:\n"
        "• Just type any question and I'll answer it\n"
        "• Send *hi* or *hello* — to greet me\n"
        "• Send *help* — to see this menu\n"
        "• Send *about* — to learn about this bot\n"
        "• Send *reset* — to start a fresh conversation\n"
        "• Send *bye* — to end the chat\n\n"
        "Or just ask me anything! 💬"
    ),
    "about": (
        "🤖 *About AswinBot*\n\n"
        "I'm an AI-powered WhatsApp assistant created by Aswin.\n"
        "I use Claude AI to understand and respond to your messages.\n"
        "I remember our conversation so feel free to ask follow-ups!\n\n"
        "🌐 Check out Aswin's portfolio: www.aswincloud.com"
    ),
    "bye": (
        "Goodbye! 👋 It was nice chatting with you.\n"
        "Feel free to message me anytime you need help. See you! 😊"
    ),
    "thanks": "You're welcome! 😊 Happy to help. Anything else?",
    "thank you": "You're welcome! 😊 Let me know if there's anything else I can help with.",
}


def get_quick_reply(text: str) -> str | None:
    return QUICK_REPLIES.get(text.strip().lower())


def ask_claude(sender: str, prompt: str) -> str | None:
    if ENABLE_USER_BUDGET and get_user_cost(sender) >= USER_BUDGET:
        return None  # budget exceeded

    history = conversation_history[sender]
    history.append({"role": "user", "content": prompt})

    if len(history) > MAX_HISTORY:
        history[:] = history[-MAX_HISTORY:]

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=600,
        system=SYSTEM_PROMPT,
        messages=history,
    )

    record_usage(sender, response.usage.input_tokens, response.usage.output_tokens)

    reply = response.content[0].text
    history.append({"role": "assistant", "content": reply})
    return reply


def mark_as_read(message_id: str):
    url = f"https://graph.facebook.com/v21.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "status": "read",
        "message_id": message_id,
    }
    requests.post(url, headers=headers, json=payload)


def sanitize_for_whatsapp(text: str) -> str:
    text = re.sub(r'\*\*(.+?)\*\*', r'*\1*', text)
    text = re.sub(r'__(.+?)__', r'_\1_', text)

    text = re.sub(r'(?<=[^\s\n])\*(\S)', r' *\1', text)
    text = re.sub(r'(\S)\*(?=[^\s\n*])', r'\1* ', text)

    text = re.sub(r'#{1,6}\s+', '', text)
    text = re.sub(r'^\[(.+?)\]\(.+?\)', r'\1', text, flags=re.MULTILINE)

    return text


def send_message(to: str, text: str):
    url = f"https://graph.facebook.com/v21.0/{PHONE_NUMBER_ID}/messages"

    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }

    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": sanitize_for_whatsapp(text)},
    }

    r = requests.post(url, headers=headers, json=payload)
    print("WhatsApp API response:", r.status_code, r.text)


def handle_admin_command(text: str) -> str | None:
    if not text.startswith("/"):
        return None

    parts = text[1:].split(None, 1)
    cmd = parts[0].lower()
    arg = parts[1].strip() if len(parts) > 1 else ""

    if cmd == "reboot":
        global _reboot_pending
        if _reboot_pending:
            return None
        _reboot_pending = True
        threading.Timer(3.0, lambda: os.execv(sys.executable, [sys.executable] + sys.argv)).start()
        return "🔄 Rebooting bot..."

    if cmd == "stats":
        usage = load_usage()
        if not usage:
            return "📊 No usage data yet."
        lines = ["📊 *Usage Stats*\n"]
        total_cost = 0.0
        for number, u in usage.items():
            cost = (u.get("input_tokens", 0) * INPUT_COST_PER_TOKEN
                    + u.get("output_tokens", 0) * OUTPUT_COST_PER_TOKEN)
            total_cost += cost
            lines.append(f"• {number}: ${cost:.4f} ({u.get('input_tokens',0)}in / {u.get('output_tokens',0)}out)")
        lines.append(f"\n💰 Total: ${total_cost:.4f}")
        return "\n".join(lines)

    if cmd == "clearall":
        conversation_history.clear()
        return "🗑️ All conversation histories cleared."

    if cmd == "addrule":
        if not arg:
            return "Usage: /addrule <rule text>"
        if len(arg) > 500:
            return "❌ Rule too long (max 500 chars)."
        prompt_file = SCRIPT_DIR / "system_prompt.txt"
        with open(prompt_file, "a", encoding="utf-8") as f:
            f.write(f"\n- {arg}")
        global SYSTEM_PROMPT
        SYSTEM_PROMPT = load_system_prompt()
        return f"✅ Rule added: {arg}"

    if cmd == "setbudget":
        if not arg:
            return "Usage: /setbudget <amount>"
        try:
            global USER_BUDGET
            USER_BUDGET = float(arg)
            cfg = load_config()
            cfg["user_budget"] = USER_BUDGET
            save_config(cfg)
            return f"✅ User budget set to ${USER_BUDGET:.2f}"
        except ValueError:
            return "❌ Invalid amount."

    if cmd == "help":
        return (
            "🔧 *Admin Commands*\n\n"
            "• */reboot* — restart the bot\n"
            "• */stats* — show usage & cost per user\n"
            "• */clearall* — clear all conversation histories\n"
            "• */addrule <text>* — append a rule to system prompt\n"
            "• */setbudget <amount>* — change per-user USD budget\n"
            "• */help* — show this menu"
        )

    return None


@app.route("/webhook", methods=["GET"])
def verify():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        return challenge, 200

    return "Verification failed", 403


@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.json

    try:
        entry = data.get("entry", [])
        if not entry:
            return "ok", 200

        changes = entry[0].get("changes", [])
        if not changes:
            return "ok", 200

        value = changes[0].get("value", {})
        messages = value.get("messages")
        if not messages:
            return "ok", 200

        message = messages[0]
        sender = message.get("from")
        message_id = message.get("id")

        if message_id:
            mark_as_read(message_id)

        if message.get("type") != "text":
            send_message(sender, "📝 I can only read text messages for now. Please send your question as text!")
            return "ok", 200

        user_text = message["text"]["body"]

        print(f"User: {sender}")
        print(f"Message: {user_text}")

        if sender == ADMIN_NUMBER and user_text.strip().startswith("/"):
            admin_reply = handle_admin_command(user_text.strip())
            if admin_reply is not None:
                send_message(sender, admin_reply)
                return "ok", 200

        if user_text.strip().lower() == "reset":
            conversation_history.pop(sender, None)
            send_message(sender, "🔄 Conversation reset! Start fresh — ask me anything.")
            return "ok", 200

        quick = get_quick_reply(user_text)
        if quick:
            if user_text.strip().lower() == "bye":
                conversation_history.pop(sender, None)
            send_message(sender, quick)
            return "ok", 200

        ai_reply = ask_claude(sender, user_text)
        if ai_reply is None:
            send_message(sender, f"⚠️ You've reached the ${USER_BUDGET:.0f} usage limit for this bot. Contact Aswin if you'd like to continue.")
            return "ok", 200

        print(f"Claude reply: {ai_reply}")
        send_message(sender, ai_reply)

    except Exception as e:
        print(f"Error processing webhook: {e}")
        traceback.print_exc()

    return "ok", 200


if __name__ == "__main__":
    send_message(ADMIN_NUMBER, "✅ Bot started and ready!")
    app.run(host="0.0.0.0", port=5000)
