import os
import time
import telebot
import threading
import requests  # Добавлено для работы с OpenRouter
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from supabase import create_client, Client
from datetime import datetime, timedelta

# --- НАСТРОЙКИ ---
TOKEN = os.environ.get('BOT_TOKEN')
URL = os.environ.get('SUPABASE_URL')
KEY = os.environ.get('SUPABASE_KEY')
# Берем ключ OpenRouter из настроек Environment Variables на Render
OPENROUTER_KEY = os.environ.get('OPENROUTER_API_KEY')

bot = telebot.TeleBot(TOKEN)
supabase: Client = create_client(URL, KEY)

app = Flask(__name__, static_folder='.')
CORS(app)

# --- ЧАСТЬ 1: ОТОБРАЖЕНИЕ ПРИЛОЖЕНИЯ ---
@app.route('/')
def serve_index():
    return send_from_directory('.', 'index.html')

# --- ЧАСТЬ 2: ОБРАБОТЧИК ИИ (OpenRouter вместо g4f) ---
@app.route('/chat', methods=['POST'])
def chat_ai():
    try:
        data = request.json
        prompt = data.get('prompt') or data.get('message') or ""
        
        if not OPENROUTER_KEY:
            return jsonify({"error": "API key not configured on Render"}), 500

        headers = {
            "Authorization": f"Bearer {OPENROUTER_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://finance-tg-app.onrender.com", # Обязательно для Render
            "X-Title": "Finance App"
        }

        payload = {
            "model": "google/gemini-2.0-flash-exp:free",
            "messages": [{"role": "user", "content": prompt}]
        }

        # Делаем официальный запрос к OpenRouter
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=25
        )

        if response.status_code != 200:
            print(f"OpenRouter Error: {response.text}")
            return jsonify({"error": "OpenRouter API error"}), response.status_code

        # Возвращаем ответ в формате, который ждет твой JS на фронтенде
        return jsonify(response.json())

    except Exception as e:
        print(f"Ошибка ИИ: {e}")
        return jsonify({"error": str(e)}), 500

# --- ЧАСТЬ 3: ТЕЛЕГРАМ БОТ ---
@bot.message_handler(commands=['start'])
def start(message):
    if "pay" in message.text:
        bot.send_invoice(
            message.chat.id,
            title="НейроСчет: Подписка",
            description="Доступ к функциям НейроСчет на 30 дней",
            invoice_payload="month_sub",
            provider_token="", 
            currency="XTR",
            prices=[telebot.types.LabeledPrice(label="Активировать НейроСчет", amount=100)],
            start_parameter="pay"
        )
    else:
        bot.send_message(
            message.chat.id, 
            "Жми кнопку НейроСчет!- запуститься Твой личный финансовый асистент разработаный на базе AI\n\nЯ."
        )

@bot.pre_checkout_query_handler(func=lambda query: True)
def checkout(query):
    bot.answer_pre_checkout_query(query.id, ok=True)

@bot.message_handler(content_types=['successful_payment'])
def success(message):
    user_id = message.from_user.id
    new_date = (datetime.now() + timedelta(days=30)).isoformat()
    try:
        supabase.table("subscriptions").upsert({
            "user_id": user_id, 
            "expires_at": new_date
        }).execute()
        bot.send_message(message.chat.id, "✅ Оплата прошла успешно!")
    except Exception as e:
        bot.send_message(message.chat.id, "⚠️ Ошибка БД. Напишите в поддержку.")

# --- ЧАСТЬ 4: ЗАПУСК ---
def run_bot_safe():
    while True:
        try:
            bot.remove_webhook()
            print("Бот НейроСчет запущен...")
            bot.infinity_polling(none_stop=True, timeout=90)
        except Exception as e:
            if "Conflict" in str(e):
                time.sleep(5)
            else:
                time.sleep(10)

if __name__ == '__main__':
    threading.Thread(target=run_bot_safe, daemon=True).start()
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
