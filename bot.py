import os
import sys
import json
import threading
from pathlib import Path
from collections import defaultdict
from datetime import datetime

import requests
from flask import Flask, request
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

MAX_HISTORY = 20
ADMIN_NUMBER = "916380157944"

client = Anthropic(api_key=ANTHROPIC_API_KEY)
app = Flask(__name__)

SCRIPT_DIR = Path(__file__).resolve().parent

def load_system_prompt():
    with open(SCRIPT_DIR / "system_prompt.txt", "r") as f:
        return f.read()

SYSTEM_PROMPT = load_system_prompt()

LOGS_DIR = SCRIPT_DIR / "logs"
LOGS_DIR.mkdir(exist_ok=True)

USAGE_FILE = SCRIPT_DIR / "usage.json"
USER_BUDGET = 10.0  # USD per user
ENABLE_USER_BUDGET = os.getenv("ENABLE_USER_BUDGET", "false").lower() == "true"

# Claude Haiku 4.5 pricing
INPUT_COST_PER_TOKEN  = 0.80 / 1_000_000
OUTPUT_COST_PER_TOKEN = 4.00 / 1_000_000


def load_usage() -> dict:
    if USAGE_FILE.exists():
        with open(USAGE_FILE, "r") as f:
            return json.load(f)
    return {}


def save_usage(usage: dict):
    with open(USAGE_FILE, "w") as f:
        json.dump(usage, f, indent=2)


def get_user_cost(sender: str) -> float:
    usage = load_usage()
    u = usage.get(sender, {})
    return (u.get("input_tokens", 0) * INPUT_COST_PER_TOKEN
            + u.get("output_tokens", 0) * OUTPUT_COST_PER_TOKEN)


def record_usage(sender: str, input_tokens: int, output_tokens: int):
    usage = load_usage()
    u = usage.setdefault(sender, {"input_tokens": 0, "output_tokens": 0})
    u["input_tokens"]  += input_tokens
    u["output_tokens"] += output_tokens
    save_usage(usage)


def log_message(sender: str, role: str, text: str):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_file = LOGS_DIR / f"{sender}.log"
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] [{role}] {text}\n")

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

    log_message(sender, "user", prompt)

    history = conversation_history[sender]
    history.append({"role": "user", "content": prompt})

    if len(history) > MAX_HISTORY:
        history[:] = history[-MAX_HISTORY:]

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=300,
        system=SYSTEM_PROMPT,
        messages=history,
    )

    record_usage(sender, response.usage.input_tokens, response.usage.output_tokens)

    reply = response.content[0].text
    history.append({"role": "assistant", "content": reply})

    log_message(sender, "bot", reply)
    return reply


def mark_as_read(message_id: str):
    url = f"https://graph.facebook.com/v19.0/{PHONE_NUMBER_ID}/messages"
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


def send_message(to: str, text: str):
    url = f"https://graph.facebook.com/v19.0/{PHONE_NUMBER_ID}/messages"

    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }

    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": text},
    }

    r = requests.post(url, headers=headers, json=payload)
    print("WhatsApp API response:", r.status_code, r.text)


ADMIN_INTENT_PROMPT = """You are a command classifier for a WhatsApp bot admin.
Given an admin message, return ONLY one of these exact keywords if the intent matches, otherwise return 'none':
- reboot       (wants to restart/reboot the bot)
- stats        (wants usage stats, user counts, cost info)
- clearall     (wants to clear all conversation histories)
- addrule      (wants to add a new rule/instruction — extract the rule text after a colon, e.g. "addrule: <rule>")
- setbudget    (wants to change the user budget — extract amount after a colon, e.g. "setbudget: <amount>")
- adminhelp    (wants to see admin commands)
- none         (not an admin command)

For addrule and setbudget, respond in the format: addrule: <rule text> or setbudget: <amount>
Only respond with the keyword or keyword: value. Nothing else."""


def detect_admin_intent(text: str) -> str:
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=50,
        system=ADMIN_INTENT_PROMPT,
        messages=[{"role": "user", "content": text}],
    )
    return response.content[0].text.strip().lower()


def handle_admin_command(cmd: str) -> str:
    cmd = cmd.strip().lower()

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

    if cmd.startswith("addrule "):
        new_rule = cmd[len("addrule "):].strip()
        if not new_rule:
            return "Usage: addrule <rule text>"
        prompt_file = SCRIPT_DIR / "system_prompt.txt"
        with open(prompt_file, "a", encoding="utf-8") as f:
            f.write(f"\n- {new_rule}")
        global SYSTEM_PROMPT
        SYSTEM_PROMPT = load_system_prompt()
        return f"✅ Rule added: {new_rule}"

    if cmd.startswith("setbudget "):
        parts = cmd.split()
        if len(parts) != 2:
            return "Usage: setbudget <amount>"
        try:
            global USER_BUDGET
            USER_BUDGET = float(parts[1])
            return f"✅ User budget set to ${USER_BUDGET:.2f}"
        except ValueError:
            return "❌ Invalid amount."

    if cmd == "adminhelp":
        return (
            "🔧 *Admin Commands*\n\n"
            "• *reboot* — restart the bot\n"
            "• *stats* — show usage & cost per user\n"
            "• *clearall* — clear all conversation histories\n"
            "• *addrule <text>* — append a rule to system prompt\n"
            "• *setbudget <amount>* — change per-user USD budget\n"
            "• *adminhelp* — show this menu"
        )

    return None  # not an admin command


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
            print(f"Skipping non-text message type: {message.get('type')}")
            return "ok", 200

        user_text = message["text"]["body"]

        print(f"User: {sender}")
        print(f"Message: {user_text}")

        if sender == ADMIN_NUMBER:
            intent = detect_admin_intent(user_text)
            if intent != "none":
                admin_reply = handle_admin_command(intent)
                if admin_reply is not None:
                    send_message(sender, admin_reply)
                    return "ok", 200

        if user_text.strip().lower() == "reset":
            conversation_history.pop(sender, None)
            send_message(sender, "🔄 Conversation reset! Start fresh — ask me anything.")
            return "ok", 200

        quick = get_quick_reply(user_text)
        if quick:
            log_message(sender, "user", user_text)
            log_message(sender, "bot", quick)
            if user_text.strip().lower() == "bye":
                conversation_history.pop(sender, None)
            send_message(sender, quick)
            return "ok", 200

        ai_reply = ask_claude(sender, user_text)
        if ai_reply is None:
            send_message(sender, "⚠️ You've reached the $10 usage limit for this bot. Contact Aswin if you'd like to continue.")
            return "ok", 200

        print(f"Claude reply: {ai_reply}")
        send_message(sender, ai_reply)

    except Exception as e:
        print(f"Error processing webhook: {e}")

    return "ok", 200


if __name__ == "__main__":
    send_message(ADMIN_NUMBER, "✅ Bot started and ready!")
    app.run(host="0.0.0.0", port=5000)
