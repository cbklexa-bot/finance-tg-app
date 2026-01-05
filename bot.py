import os
import telebot
import threading
import http.server
import socketserver
from supabase import create_client, Client
from datetime import datetime, timedelta

# --- БЛОК ДЛЯ СТАБИЛЬНОЙ РАБОТЫ НА RENDER (Health Check) ---
def run_health_server():
    handler = http.server.SimpleHTTPRequestHandler
    port = int(os.environ.get("PORT", 10000))
    with socketserver.TCPServer(("", port), handler) as httpd:
        print(f"Health check server running on port {port}")
        httpd.serve_forever()

threading.Thread(target=run_health_server, daemon=True).start()
# -----------------------------------------------------------

# Загрузка ключей из переменных окружения Render
TOKEN = os.environ.get('BOT_TOKEN')
URL = os.environ.get('SUPABASE_URL')
KEY = os.environ.get('SUPABASE_KEY')

bot = telebot.TeleBot(TOKEN)
supabase: Client = create_client(URL, KEY)

@bot.message_handler(commands=['start'])
def start(message):
    # Проверяем, пришел ли пользователь из приложения по ссылке ?start=pay
    if "pay" in message.text:
        bot.send_invoice(
            message.chat.id,
            title="НейроСчет: Подписка",
            description="Доступ к функциям НейроСчет на 30 дней",
            invoice_payload="month_sub",
            provider_token="", # Для Telegram Stars всегда пусто
            currency="XTR",    # Валюта: Telegram Stars
            prices=[telebot.types.LabeledPrice(label="Активировать НейроСчет", amount=100)], # 100 звезд ≈ 199 руб
            start_parameter="pay"
        )
    else:
        bot.send_message(message.chat.id, "Добро пожаловать в НейроСчет! Используйте Mini App для управления финансами.")

@bot.pre_checkout_query_handler(func=lambda query: True)
def checkout(query):
    bot.answer_pre_checkout_query(query.id, ok=True)

@bot.message_handler(content_types=['successful_payment'])
def success(message):
    user_id = message.from_user.id
    # Рассчитываем новую дату (текущая дата + 30 дней)
    new_date = (datetime.now() + timedelta(days=30)).isoformat()
    
    try:
        # Автоматическое обновление подписки в Supabase
        supabase.table("subscriptions").upsert({
            "user_id": user_id, 
            "expires_at": new_date
        }).execute()
        
        bot.send_message(message.chat.id, "✅ Оплата прошла успешно! Ваш доступ к НейроСчет продлен на 30 дней. Перезапустите приложение.")
    except Exception as e:
        print(f"Ошибка Supabase: {e}")
        bot.send_message(message.chat.id, "⚠️ Оплата прошла, но возникла ошибка при обновлении базы. Пожалуйста, напишите в поддержку.")

print("Бот НейроСчет запущен и готов к работе...")
bot.polling(none_stop=True)
