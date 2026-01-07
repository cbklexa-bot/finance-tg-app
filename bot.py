import os
import time
import threading
import telebot
from flask import Flask, request, jsonify, send_file
from supabase import create_client, Client
from datetime import datetime, timedelta
import g4f

# --- НАСТРОЙКИ ---
TOKEN = os.environ.get('BOT_TOKEN')
URL = os.environ.get('SUPABASE_URL')
KEY = os.environ.get('SUPABASE_KEY')

# Инициализация
bot = telebot.TeleBot(TOKEN)
supabase: Client = create_client(URL, KEY)
app = Flask(__name__)

# --- ЧАСТЬ 1: ВЕБ-СЕРВЕР (FLASK) ---

# ГЛАВНАЯ СТРАНИЦА: Теперь загружает твой index.html
@app.route('/')
def index():
    try:
        # Мы ищем файл index.html в той же папке
        return send_file('index.html')
    except Exception as e:
        return f"Ошибка при загрузке приложения: {e}", 500

# ОБРАБОТЧИК AI: Сюда стучится твое приложение
@app.route('/chat', methods=['POST'])
def chat_ai():
    try:
        data = request.json
        prompt = data.get('prompt', '')
        
        # Запрос к бесплатному ИИ
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
        print(f"Ошибка AI: {e}")
        return jsonify({"error": "AI service error", "details": str(e)}), 500

# --- ЧАСТЬ 2: ТЕЛЕГРАМ БОТ ---

@bot.message_handler(commands=['start'])
def start(message):
    # Если запуск с параметром оплаты
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
        # Обычный запуск - кнопка
        markup = telebot.types.InlineKeyboardMarkup()
        # ВАЖНО: Убедись, что тут ссылка на твой Render
        btn = telebot.types.InlineKeyboardButton(
            "🚀 Открыть НейроСчет", 
            web_app=telebot.types.WebAppInfo(url="https://finance-tg-app.onrender.com")
        )
        markup.add(btn)
        
        bot.send_message(
            message.chat.id, 
            "Добро пожаловать в НейроСчет!\n\nТвой финансовый ассистент с ИИ.",
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
        bot.send_message(message.chat.id, "✅ Подписка продлена! Перезапустите приложение.")
    except Exception as e:
        print(f"Ошибка БД: {e}")
        bot.send_message(message.chat.id, "⚠️ Ошибка сохранения подписки. Напишите в поддержку.")

# --- ЗАПУСК ---

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    # host='0.0.0.0' делает сайт доступным из интернета
    app.run(host="0.0.0.0", port=port)

if __name__ == "__main__":
    # 1. Лечим ошибку сети
    try:
        print("Сброс вебхука...")
        bot.remove_webhook()
        time.sleep(1)
    except:
        pass

    # 2. Запускаем сервер сайта (в фоне)
    t = threading.Thread(target=run_flask)
    t.daemon = True
    t.start()

    # 3. Запускаем бота
    print("Бот и Приложение запущены...")
    bot.infinity_polling(skip_pending=True)
    # 3. Запускаем бота (infinity_polling лучше обычного polling)
    print("Запускаю бота...")
    bot.infinity_polling(skip_pending=True)
