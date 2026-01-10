import os
import json
import re
from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
from supabase import create_client
import telebot

# --- CONFIG ---
BOT_TOKEN = os.environ.get("BOT_TOKEN")
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
OPENROUTER_KEY = os.environ.get("OPENROUTER_API_KEY")
RENDER_URL = os.environ.get("RENDER_EXTERNAL_URL")  # Render даёт сам

bot = telebot.TeleBot(BOT_TOKEN)
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

app = Flask(__name__)
CORS(app)

# --- WEBHOOK ---
WEBHOOK_PATH = f"/webhook/{BOT_TOKEN}"
WEBHOOK_URL = RENDER_URL + WEBHOOK_PATH


@app.route(WEBHOOK_PATH, methods=["POST"])
def telegram_webhook():
    update = telebot.types.Update.de_json(request.json)
    bot.process_new_updates([update])
    return "OK", 200


@app.route("/")
def health():
    return "Bot is running", 200


# --- TELEGRAM HANDLERS ---
@bot.message_handler(commands=["start"])
def start(msg):
    bot.send_message(msg.chat.id, "Привет! Я твой финансовый ассистент 💰")


@bot.message_handler(func=lambda m: True)
def handle_message(msg):
    user_id = msg.chat.id
    text = msg.text

    # Отправляем в AI
    r = requests.post(
        f"{RENDER_URL}/chat",
        json={"prompt": text, "user_id": user_id},
        timeout=60
    )

    if r.ok:
        reply = r.json()["choices"][0]["message"]["content"]
        bot.send_message(user_id, reply)
    else:
        bot.send_message(user_id, "Ошибка обработки запроса")


# --- AI ENDPOINT ---
@app.route("/chat", methods=["POST"])
def chat_ai():
    data = request.json
    prompt = data.get("prompt", "")
    user_id = str(data.get("user_id"))

    # История
    res = supabase.table("finance").select("data").eq("user_id", user_id).execute()
    history = res.data or []

    history_text = "\n".join(
        f"- {x['data']['d']} | {x['data']['t']} | {x['data']['c']} | {x['data']['s']} ₽"
        for x in history
    ) or "История пуста."

    system = f"""
Ты финансовый ассистент.
Сегодня {datetime.now().date()}.

Категории доходов:
💵 Зарплата, 📈 Инвест, 🎁 Подарок, 📦 Прочее

Категории расходов:
🛒 Продукты, 🚗 Авто, 🏠 Жильё, 🎭 Отдых, 💊 Аптека, 🛍️ Шопинг

Формат записи:
[JSON_DATA]{{"t":"exp|inc","c":"категория","s":число,"n":"описание"}}[/JSON_DATA]

ИСТОРИЯ:
{history_text}
"""

    response = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={"Authorization": f"Bearer {OPENROUTER_KEY}"},
        json={
            "model": "deepseek/deepseek-chat",
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
        },
        timeout=60,
    ).json()

    msg = response["choices"][0]["message"]["content"]

    if "[JSON_DATA]" in msg:
        m = re.search(r"\[JSON_DATA\](.*?)\[/JSON_DATA\]", msg, re.S)
        tx = json.loads(m.group(1))
        tx["d"] = datetime.now().strftime("%Y-%m-%d")
        tx["id"] = int(datetime.now().timestamp() * 1000)

        supabase.table("finance").insert(
            {"user_id": user_id, "data": tx}
        ).execute()

        msg = re.sub(r"\[JSON_DATA\].*?\[/JSON_DATA\]", "", msg, flags=re.S).strip()

    return jsonify({"choices": [{"message": {"content": msg}}]})


# --- START ---
if __name__ == "__main__":
    bot.remove_webhook()
    bot.set_webhook(url=WEBHOOK_URL)

    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
