import os
import telebot
import threading
import http.server
import socketserver
from supabase import create_client, Client
from datetime import datetime, timedelta

# --- ЭТОТ БЛОК НУЖЕН ДЛЯ RENDER (Health Check) ---
def run_health_server():
    handler = http.server.SimpleHTTPRequestHandler
    port = int(os.environ.get("PORT", 10000))
    with socketserver.TCPServer(("", port), handler) as httpd:
        print(f"Serving health check on port {port}")
        httpd.serve_forever()

threading.Thread(target=run_health_server, daemon=True).start()
# ------------------------------------------------

TOKEN = os.environ.get('BOT_TOKEN')
URL = os.environ.get('SUPABASE_URL')
KEY = os.environ.get('SUPABASE_KEY')

bot = telebot.TeleBot(TOKEN)
supabase: Client = create_client(URL, KEY)

@bot.message_handler(commands=['start'])
def start(message):
    # Если зашли по ссылке ?start=pay
    if "pay" in message.text:
        bot.send_invoice(
            message.chat.id,
            title="Подписка на 30 дней",
            description="Доступ к приложению Копилка",
            invoice_payload="month_sub",
            provider_token="", # Для Stars всегда пусто
            currency="XTR",    # Валюта Stars
            prices=[telebot.types.LabeledPrice(label="Продлить", amount=100)],
            start_parameter="pay"
        )
    else:
        bot.send_message(message.chat.id, "Бот активен! Оплатите подписку через приложение.")

@bot.pre_checkout_query_handler(func=lambda query: True)
def checkout(query):
    bot.answer_pre_checkout_query(query.id, ok=True)

@bot.message_handler(content_types=['successful_payment'])
def success(message):
    user_id = message.from_user.id
    new_date = (datetime.now() + timedelta(days=30)).isoformat()
    # Обновляем Supabase автоматически
    supabase.table("subscriptions").upsert({
        "user_id": user_id, 
        "expires_at": new_date
    }).execute()
    bot.send_message(message.chat.id, "✅ Оплата принята! Подписка продлена.")

print("Бот запущен...")
bot.polling(none_stop=True)
