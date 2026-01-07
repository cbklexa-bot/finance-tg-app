import os
import time
import threading
import telebot
from flask import Flask, request, jsonify
from supabase import create_client, Client
from datetime import datetime, timedelta
import g4f # Библиотека для работы ИИ

# --- НАСТРОЙКИ ---
TOKEN = os.environ.get('BOT_TOKEN')
URL = os.environ.get('SUPABASE_URL')
KEY = os.environ.get('SUPABASE_KEY')

# Инициализация
bot = telebot.TeleBot(TOKEN)
supabase: Client = create_client(URL, KEY)
app = Flask(__name__)

# --- ЧАСТЬ 1: СЕРВЕР ДЛЯ ИИ (FLASK) ---

@app.route('/')
def health_check():
    # Просто чтобы Render знал, что мы живы
    return "NeyroSchet AI Server is running", 200

@app.route('/chat', methods=['POST'])
def chat_ai():
    try:
        # Получаем текст от сайта
        data = request.json
        prompt = data.get('prompt', '')
        
        # Запрашиваем ответ у ИИ (используем gpt-3.5 или 4o-mini через g4f)
        response = g4f.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            stream=False
        )
        
        # Отправляем ответ обратно на сайт
        return jsonify({
            "choices": [{
                "message": {
                    "content": response
                }
            }]
        })

    except Exception as e:
        print(f"Ошибка AI: {e}")
        return jsonify({"error": "AI service error", "details": str(e)}), 500

# --- ЧАСТЬ 2: ТЕЛЕГРАМ БОТ ---

@bot.message_handler(commands=['start'])
def start(message):
    # Проверка на параметр оплаты ?start=pay
    if len(message.text.split()) > 1 and "pay" in message.text.split()[1]:
        bot.send_invoice(
            message.chat.id,
            title="НейроСчет: Подписка",
            description="Доступ к функциям НейроСчет на 30 дней",
            invoice_payload="month_sub",
            provider_token="", 
            currency="XTR",
            prices=[telebot.types.LabeledPrice(label="Активировать", amount=100)], 
            start_parameter="pay"
        )
    else:
        # Обычный вход - показываем кнопку
        markup = telebot.types.InlineKeyboardMarkup()
        # ВАЖНО: Убедись, что ссылка правильная (твоего Mini App)
        btn = telebot.types.InlineKeyboardButton(
            "🚀 Открыть НейроСчет", 
            web_app=telebot.types.WebAppInfo(url="https://finance-tg-app.onrender.com")
        )
        markup.add(btn)
        
        bot.send_message(
            message.chat.id, 
            "Добро пожаловать в НейроСчет!\n\nТвой финансовый ассистент с ИИ.\nНажми кнопку ниже, чтобы начать:",
            reply_markup=markup
        )

# Обработка предварительного запроса оплаты
@bot.pre_checkout_query_handler(func=lambda query: True)
def checkout(query):
    bot.answer_pre_checkout_query(query.id, ok=True)

# Обработка успешной оплаты
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
        print(f"Ошибка БД: {e}")
        bot.send_message(message.chat.id, "⚠️ Оплата прошла, но возникла ошибка сохранения. Напишите в поддержку.")

# --- ЗАПУСК ВСЕГО ВМЕСТЕ ---

def run_flask():
    # Запускаем сервер на порту 10000 (для Render)
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

if __name__ == "__main__":
    # 1. Сбрасываем старые вебхуки, чтобы бот не тупил
    try:
        print("Сброс вебхука...")
        bot.remove_webhook()
        time.sleep(1)
    except Exception as e:
        print(e)

    # 2. Запускаем Flask (для ИИ) в отдельном потоке
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()

    # 3. Запускаем Бота (основной процесс)
    print("Бот и ИИ сервер запущены...")
    bot.infinity_polling(skip_pending=True)
