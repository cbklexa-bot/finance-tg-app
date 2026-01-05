import os
import telebot
import threading
import requests
import time
from flask import Flask, request, Response
from flask_cors import CORS
from supabase import create_client, Client
from datetime import datetime, timedelta

# --- НАСТРОЙКИ ---
TOKEN = os.environ.get('BOT_TOKEN')
URL = "https://ereiiidezagburttpxtn.supabase.co"
KEY = os.environ.get('SUPABASE_KEY')

app = Flask(__name__)
CORS(app)

bot = telebot.TeleBot(TOKEN)
supabase: Client = create_client(URL, KEY)

# --- ПРОКСИ-СЕРВЕР ---
@app.route('/proxy/<path:url>', methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'])
def supabase_proxy(url):
    target_url = f"{URL}/{url}"
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
    # Threaded=True позволяет Flask обрабатывать несколько запросов одновременно
    app.run(host='0.0.0.0', port=port, threaded=True)

# --- ЛОГИКА БОТА ---
@bot.message_handler(commands=['start'])
def start(message):
    if "pay" in message.text:
        bot.send_invoice(
            message.chat.id,
            title="НейроСчет: Подписка",
            description="Доступ на 30 дней",
            invoice_payload="month_sub",
            provider_token="", 
            currency="XTR",
            prices=[telebot.types.LabeledPrice(label="Активировать", amount=100)],
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
        bot.send_message(message.chat.id, f"⚠️ Ошибка базы: {e}")

if __name__ == "__main__":
    # 1. Запускаем веб-сервер в отдельном потоке
    threading.Thread(target=run_flask, daemon=True).start()
    
    # 2. Очищаем старые подключения (лечит ошибку 409)
    bot.remove_webhook()
    time.sleep(1)
    
    print("Система запущена (Proxy + Bot)...")
    
    # 3. Запускаем бота в основном потоке (infinity_polling лучше для Render)
    bot.infinity_polling(skip_pending=True)
