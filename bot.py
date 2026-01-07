import os
import time
import telebot
import threading
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from supabase import create_client, Client
from datetime import datetime, timedelta
import g4f

# --- НАСТРОЙКИ ---
TOKEN = os.environ.get('BOT_TOKEN')
URL = os.environ.get('SUPABASE_URL')
KEY = os.environ.get('SUPABASE_KEY')

bot = telebot.TeleBot(TOKEN)
supabase: Client = create_client(URL, KEY)

# Указываем Flask, что статические файлы лежат в той же папке
app = Flask(__name__, static_folder='.')
CORS(app)

# --- ЧАСТЬ 1: ОТОБРАЖЕНИЕ ПРИЛОЖЕНИЯ (INDEX.HTML) ---
@app.route('/')
def serve_index():
    # Теперь по главной ссылке откроется твое приложение, а не надпись
    return send_from_directory('.', 'index.html')

# --- ЧАСТЬ 2: ОБРАБОТЧИК ИИ (AI) ---
@app.route('/chat', methods=['POST'])
def chat_ai():
    try:
        data = request.json
        prompt = data.get('prompt') or data.get('message') or ""
        
        response = g4f.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            stream=False
        )
        
        return jsonify({
            "choices": [{
                "message": {
                    "content": response
                }
            }]
        })
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
            "🦁 Добро пожаловать в НейроСчет!\n\nЯ готов помогать тебе с финансами. Используй кнопку в меню или в строке ввода, чтобы запустить приложение."
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
