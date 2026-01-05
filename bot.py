import os
import telebot
from supabase import create_client, Client
from datetime import datetime, timedelta

# Берем ключи из настроек Render
TOKEN = os.environ.get('BOT_TOKEN')
URL = os.environ.get('SUPABASE_URL')
KEY = os.environ.get('SUPABASE_KEY')

bot = telebot.TeleBot(TOKEN)
supabase: Client = create_client(URL, KEY)

@bot.message_handler(commands=['start'])
def start(message):
    if "pay" in message.text:
        bot.send_invoice(
            message.chat.id,
            title="Подписка на 30 дней",
            description="Доступ к приложению Копилка",
            invoice_payload="month_sub",
            provider_token="",
            currency="XTR",
            prices=[telebot.types.LabeledPrice(label="Продлить", amount=199)],
            start_parameter="pay"
        )
    else:
        bot.send_message(message.chat.id, "Используйте приложение для управления финансами.")

@bot.pre_checkout_query_handler(func=lambda query: True)
def checkout(query):
    bot.answer_pre_checkout_query(query.id, ok=True)

@bot.message_handler(content_types=['successful_payment'])
def success(message):
    new_date = (datetime.now() + timedelta(days=30)).isoformat()
    supabase.table("subscriptions").upsert({"user_id": message.from_user.id, "expires_at": new_date}).execute()
    bot.send_message(message.chat.id, "✅ Подписка продлена!")

bot.polling(none_stop=True)
