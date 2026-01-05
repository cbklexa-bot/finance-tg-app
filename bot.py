import os
import telebot
import threading
import requests
from flask import Flask, request, Response
from flask_cors import CORS
from supabase import create_client, Client
from datetime import datetime, timedelta

# --- НАСТРОЙКИ ---
TOKEN = os.environ.get('BOT_TOKEN')
# Твои данные Supabase
URL = "https://ereiiidezagburttpxtn.supabase.co"
KEY = os.environ.get('SUPABASE_KEY') # Ключ лучше оставить в переменных Render

app = Flask(__name__)
CORS(app) # Разрешаем доступ из Mini App

bot = telebot.TeleBot(TOKEN)
supabase: Client = create_client(URL, KEY)

# --- ПРОКСИ-СЕРВЕР ---
@app.route('/proxy/<path:url>', methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'])
def supabase_proxy(url):
    target_url = f"{URL}/{url}"
    # Копируем заголовки, убирая Host
    headers = {k: v for k, v in request.headers if k.lower() != 'host'}
    
    try:
        resp = requests.request(
            method=request.method,
            url=target_url,
            headers=headers,
            data=request.get_data(),
            params=request.args,
            timeout=10
        )
        # Убираем опасные заголовки перед отправкой обратно
        excluded_headers = ['content-encoding', 'transfer-encoding', 'content-length', 'connection']
        proxy_headers = [(k, v) for k, v in resp.headers.items() if k.lower() not in excluded_headers]
        
        return Response(resp.content, resp.status_code, proxy_headers)
    except Exception as e:
        return {"error": str(e)}, 500

@app.route('/')
def health():
    return "Proxy and Bot are running", 200

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# Запуск сервера в фоне
threading.Thread(target=run_flask, daemon=True).start()

# --- ЛОГИКА БОТА ---
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
        bot.send_message(message.chat.id, "Добро пожаловать в НейроСчет! Откройте приложение.")

@bot.pre_checkout_query_handler(func=lambda query: True)
def checkout(query):
    bot.answer_pre_checkout_query(query.id, ok=True)

@bot.message_handler(content_types=['successful_payment'])
def success(message):
    user_id = message.from_user.id
    new_date = (datetime.now() + timedelta(days=30)).isoformat()
    try:
        supabase.table("subscriptions").upsert({"user_id": user_id, "expires_at": new_date}).execute()
        bot.send_message(message.chat.id, "✅ Оплата прошла! Доступ продлен.")
    except Exception as e:
        bot.send_message(message.chat.id, "⚠️ Ошибка обновления базы.")

print("Система запущена...")
bot.polling(none_stop=True)
