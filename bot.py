import os
import time
import telebot
import threading
from flask import Flask, request, jsonify
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

app = Flask(__name__)
CORS(app)  # Разрешаем Mini App обращаться к серверу (для AI без VPN)

# --- ЧАСТЬ 1: ОБРАБОТЧИК ИИ (AI) ДЛЯ ПРИЛОЖЕНИЯ ---
@app.route('/chat', methods=['POST'])
def chat_ai():
    try:
        data = request.json
        prompt = data.get('prompt') or data.get('message') or ""
        
        # Запрос к нейросети через бесплатный провайдер
        response = g4f.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            stream=False
        )
        
        # Возвращаем формат, который ожидает твой index.html
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

@app.route('/')
def health():
    return "НейроСчет: Бот и Сервер активны", 200

# --- ЧАСТЬ 2: ТЕЛЕГРАМ БОТ (КОМАНДЫ И ОПЛАТА) ---

@bot.message_handler(commands=['start'])
def start(message):
    # Если пользователь пришел по ссылке на оплату
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
        # Просто текстовое приветствие без кнопки (кнопка уже есть в меню/строке ввода)
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
        # Сохраняем информацию о подписке в базу
        supabase.table("subscriptions").upsert({
            "user_id": user_id, 
            "expires_at": new_date
        }).execute()
        bot.send_message(message.chat.id, "✅ Оплата прошла успешно! Доступ к НейроСчет продлен на 30 дней. Можешь возвращаться в приложение.")
    except Exception as e:
        print(f"Ошибка БД: {e}")
        bot.send_message(message.chat.id, "⚠️ Оплата прошла, но возникла ошибка обновления в базе. Напишите в поддержку.")

# --- ЧАСТЬ 3: СТАБИЛЬНЫЙ ЗАПУСК И ЗАЩИТА ---

def run_bot_safe():
    while True:
        try:
            bot.remove_webhook()
            print("Бот НейроСчет запущен...")
            bot.infinity_polling(none_stop=True, timeout=90, long_polling_timeout=90)
        except Exception as e:
            if "Conflict" in str(e):
                print("Ошибка Conflict (409). Ждем завершения старого процесса...")
                time.sleep(5)
            else:
                print(f"Ошибка бота: {e}. Перезапуск через 10 сек...")
                time.sleep(10)

if __name__ == '__main__':
    # 1. Запускаем Telegram бота в отдельном потоке
    threading.Thread(target=run_bot_safe, daemon=True).start()
    
    # 2. Запускаем Flask сервер на порту Render (для AI чата)
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
