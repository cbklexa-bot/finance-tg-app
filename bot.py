import os
import time
import threading
import telebot
from flask import Flask, request, jsonify, send_file
from supabase import create_client, Client
from datetime import datetime, timedelta
import g4f  # Библиотека для бесплатного ИИ

# --- НАСТРОЙКИ (БЕРУТСЯ ИЗ RENDER) ---
TOKEN = os.environ.get('BOT_TOKEN')
URL = os.environ.get('SUPABASE_URL')
KEY = os.environ.get('SUPABASE_KEY')

# Инициализация
bot = telebot.TeleBot(TOKEN)
supabase: Client = create_client(URL, KEY)
app = Flask(__name__)

# --- ЧАСТЬ 1: ВЕБ-СЕРВЕР (FLASK) ДЛЯ ПРИЛОЖЕНИЯ И ИИ ---

# 1. Отдача самого приложения (index.html)
@app.route('/')
def index():
    try:
        # Теперь по адресу твоего сайта будет открываться само приложение
        return send_file('index.html')
    except Exception as e:
        return f"Ошибка загрузки index.html: {e}", 500

# 2. Обработчик для ИИ (исправляет ошибку 501 / 404 в приложении)
@app.route('/chat', methods=['POST'])
def chat_ai():
    try:
        data = request.json
        prompt = data.get('prompt', '')
        
        # Запрос к нейросети через g4f
        response = g4f.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            stream=False
        )
        
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

# --- ЧАСТЬ 2: ТЕЛЕГРАМ БОТ (КОМАНДЫ И ОПЛАТА) ---

@bot.message_handler(commands=['start'])
def start(message):
    # Если пользователь пришел по ссылке для оплаты
    if len(message.text.split()) > 1 and "pay" in message.text.split()[1]:
        bot.send_invoice(
            message.chat.id,
            title="НейроСчет: Подписка",
            description="Доступ к функциям на 30 дней",
            invoice_payload="month_sub",
            provider_token="", 
            currency="XTR",
            prices=[telebot.types.LabeledPrice(label="Активировать", amount=100)], 
            start_parameter="pay"
        )
    else:
        # Обычное приветствие с кнопкой запуска приложения
        markup = telebot.types.InlineKeyboardMarkup()
        # ЗАМЕНИ URL НИЖЕ НА СВОЙ URL ИЗ RENDER, ЕСЛИ ОН ДРУГОЙ
        web_app_url = "https://finance-tg-app.onrender.com"
        btn = telebot.types.InlineKeyboardButton("🚀 Открыть НейроСчет", web_app=telebot.types.WebAppInfo(url=web_app_url))
        markup.add(btn)
        
        bot.send_message(
            message.chat.id, 
            "Привет! Я Финни. 🦁\nПомогу навести порядок в деньгах.\n\nНажми кнопку ниже, чтобы запустить приложение:",
            reply_markup=markup
        )

# Обработка платежа
@bot.pre_checkout_query_handler(func=lambda query: True)
def checkout(query):
    bot.answer_pre_checkout_query(query.id, ok=True)

@bot.message_handler(content_types=['successful_payment'])
def success(message):
    user_id = message.from_user.id
    new_date = (datetime.now() + timedelta(days=30)).isoformat()
    try:
        supabase.table("subscriptions").upsert({"user_id": user_id, "expires_at": new_date}).execute()
        bot.send_message(message.chat.id, "✅ Оплата прошла! Подписка продлена на 30 дней.")
    except Exception as e:
        bot.send_message(message.chat.id, "Оплата прошла, но в БД ошибка. Напишите в поддержку.")

# --- ЧАСТЬ 3: ЗАПУСК ВСЕЙ СИСТЕМЫ ---

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

if __name__ == "__main__":
    # 1. Удаляем вебхуки, чтобы не было конфликтов
    try:
        bot.remove_webhook()
        time.sleep(1)
    except:
        pass

    # 2. Запускаем Flask в отдельном потоке
    threading.Thread(target=run_flask, daemon=True).start()

    # 3. Бесконечный цикл запуска бота (защита от падений и Conflict 409)
    print("Система запущена: Бот + Приложение + ИИ")
    while True:
        try:
            bot.infinity_polling(skip_pending=True, timeout=90, long_polling_timeout=90)
        except Exception as e:
            # Если видим ошибку "Conflict", просто ждем и пробуем снова
            print(f"Заминка бота: {e}")
            time.sleep(5)
