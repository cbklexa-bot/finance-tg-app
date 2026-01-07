import os
import time
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
    # Проверяем, пришел ли пользователь по ссылке ?start=pay
    if len(message.text.split()) > 1 and "pay" in message.text.split()[1]:
        bot.send_invoice(
            message.chat.id,
            title="НейроСчет: Подписка",
            description="Доступ к функциям НейроСчет на 30 дней",
            invoice_payload="month_sub",
            provider_token="", # Для Telegram Stars всегда пусто
            currency="XTR",    # Валюта: Telegram Stars
            prices=[telebot.types.LabeledPrice(label="Активировать НейроСчет", amount=100)], 
            start_parameter="pay"
        )
    else:
        # Приветственное сообщение + Кнопка запуска
        markup = telebot.types.InlineKeyboardMarkup()
        btn = telebot.types.InlineKeyboardButton("🚀 Открыть НейроСчет", web_app=telebot.types.WebAppInfo(url="https://finance-tg-app.onrender.com")) # УБЕДИСЬ, ЧТО ТУТ ТВОЯ ССЫЛКА
        markup.add(btn)
        
        bot.send_message(
            message.chat.id, 
            "Добро пожаловать в НейроСчет!\n\nЭто твой личный финансовый ассистент. Нажми кнопку ниже, чтобы начать.",
            reply_markup=markup
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
        
        bot.send_message(message.chat.id, "✅ Оплата прошла успешно! Ваш доступ продлен на 30 дней. Перезапустите приложение.")
    except Exception as e:
        print(f"Ошибка Supabase: {e}")
        bot.send_message(message.chat.id, "⚠️ Оплата прошла, но возникла ошибка при сохранении. Напишите в поддержку.")

if __name__ == "__main__":
    # ВАЖНО: Удаляем старый вебхук перед запуском опроса
    print("Сбрасываем вебхук...")
    bot.remove_webhook()
    time.sleep(1)
    
    print("Бот НейроСчет запущен...")
    # skip_pending=True, чтобы бот не отвечал на старые сообщения, которые накопились пока он лежал
    bot.infinity_polling(skip_pending=True)
