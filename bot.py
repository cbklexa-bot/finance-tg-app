import os
import telebot
import threading
import requests
from flask import Flask, request, Response
from flask_cors import CORS
from supabase import create_client, Client
from datetime import datetime, timedelta

# --- НАСТРОЙКА FLASK (ПРОКСИ И HEALTH CHECK) ---
app = Flask(__name__)
CORS(app)  # Разрешаем запросы от Mini App

# Данные Supabase
URL = os.environ.get('SUPABASE_URL') # Например: https://xyz.supabase.co
KEY = os.environ.get('SUPABASE_KEY')
TOKEN = os.environ.get('BOT_TOKEN')

bot = telebot.TeleBot(TOKEN)
supabase: Client = create_client(URL, KEY)

# Маршрут для проксирования запросов к Supabase
@app.route('/proxy/<path:url>', methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'])
def supabase_proxy(url):
    # Формируем реальный адрес в Supabase
    target_url = f"{URL}/{url}"
    
    # Копируем заголовки из запроса приложения (кроме Host)
    headers = {k: v for k, v in request.headers if k.lower() != 'host'}
    
    try:
        # Отправляем запрос от имени сервера Render в Supabase
        resp = requests.request(
            method=request.method,
            url=target_url,
            headers=headers,
            data=request.get_data(),
            params=request.args,
            timeout=10
        )
        
        # Передаем ответ обратно в Mini App
        excluded_headers = ['content-encoding', 'transfer-encoding', 'content-length', 'connection']
        proxy_headers = [(k, v) for k, v in resp.headers.items() if k.lower() not in excluded_headers]
        
        return Response(resp.content, resp.status_code, proxy_headers)
    except Exception as e:
        return {"error": str(e)}, 500

# Оставляем стандартный путь для проверки Render
@app.route('/')
def health():
    return "OK", 200

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# Запускаем Flask в отдельном потоке
threading.Thread(target=run_flask, daemon=True).start()

# --- ЛОГИКА БОТА (БЕЗ ИЗМЕНЕНИЙ) ---

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
        bot.send_message(message.chat.id, "Добро пожаловать в НейроСчет! Используйте Mini App.")

@bot.pre_checkout_query_handler(func=lambda query: True)
def checkout(query):
    bot.answer_pre_checkout_query(query.id, ok=True)

@bot.message_handler(content_types=['successful_payment'])
def success(message):
    user_id = message.from_user.id
    new_date = (datetime.now() + timedelta(days=30)).isoformat()
    try:
        supabase.table("subscriptions").upsert({"user_id": user_id, "expires_at": new_date}).execute()
        bot.send_message(message.chat.id, "✅ Оплата прошла успешно! Перезапустите приложение.")
    except Exception as e:
        bot.send_message(message.chat.id, "⚠️ Ошибка обновления базы.")

print("Бот и Прокси запущены...")
bot.polling(none_stop=True)
