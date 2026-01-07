import os
import time
import threading
import telebot
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS  # Добавили для работы бюджета
from supabase import create_client, Client
from datetime import datetime, timedelta
import g4f

# --- НАСТРОЙКИ ---
TOKEN = os.environ.get('BOT_TOKEN')
URL = os.environ.get('SUPABASE_URL')
KEY = os.environ.get('SUPABASE_KEY')

bot = telebot.TeleBot(TOKEN)
supabase: Client = create_client(URL, KEY)

app = Flask(__name__, static_folder='.')
CORS(app) # Разрешаем приложению подгружать данные из БД

# --- СЕРВЕРНАЯ ЧАСТЬ (ДЛЯ ИИ И ПРИЛОЖЕНИЯ) ---

@app.route('/')
def index():
    # Отдаем твой index.html
    return send_from_directory('.', 'index.html')

@app.route('/chat', methods=['POST'])
def chat_ai():
    try:
        data = request.json
        prompt = data.get('prompt', '')
        
        # Запрос к ИИ
        response = g4f.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            stream=False
        )
        
        # Возвращаем в формате, который понимает твой index.html
        return jsonify({
            "choices": [{"message": {"content": response}}]
        })
    except Exception as e:
        print(f"Ошибка ИИ: {e}")
        return jsonify({"error": str(e)}), 500

# --- БОТ (КОМАНДЫ И ОПЛАТА ИЗ ТВОЕГО КОДА) ---

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
        # Добавляем кнопку открытия, чтобы было удобно
        markup = telebot.types.InlineKeyboardMarkup()
        btn = telebot.types.InlineKeyboardButton(
            "🚀 Открыть НейроСчет", 
            web_app=telebot.types.WebAppInfo(url="https://finance-tg-app.onrender.com")
        )
        markup.add(btn)
        bot.send_message(message.chat.id, "Добро пожаловать! Используйте Mini App для управления финансами.", reply_markup=markup)

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
        bot.send_message(message.chat.id, "✅ Оплата прошла успешно! Перезапустите приложение.")
    except Exception as e:
        print(f"Ошибка Supabase: {e}")
        bot.send_message(message.chat.id, "⚠️ Ошибка обновления базы. Напишите в поддержку.")

# --- ЗАПУСК ---

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

if __name__ == "__main__":
    # Запускаем сайт/ИИ
    threading.Thread(target=run_flask, daemon=True).start()
    
    # Запускаем бота (с защитой от вылетов)
    print("Бот НейроСчет запущен...")
    while True:
        try:
            bot.infinity_polling(skip_pending=True, timeout=90)
        except Exception as e:
            print(f"Перезапуск бота: {e}")
            time.sleep(5)
