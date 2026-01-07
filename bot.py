import os
import time
import threading
import telebot
from flask import Flask, request, jsonify
from supabase import create_client, Client
from datetime import datetime, timedelta

# --- НАСТРОЙКИ ---
TOKEN = os.environ.get('BOT_TOKEN')
URL = os.environ.get('SUPABASE_URL')
KEY = os.environ.get('SUPABASE_KEY')

# Инициализация
bot = telebot.TeleBot(TOKEN)
supabase: Client = create_client(URL, KEY)
app = Flask(__name__)

# --- ЛОГИКА FLASK (СЕРВЕР ДЛЯ AI И HEALTH CHECK) ---

@app.route('/')
def health_check():
    return "App is running", 200

# Обработчик AI (исправляет ошибку 501)
@app.route('/chat', methods=['POST'])
def chat_ai():
    try:
        data = request.json
        prompt = data.get('prompt', '')
        # history = data.get('history', []) # Можно использовать для контекста

        # --- ЗДЕСЬ ТВОЯ ЛОГИКА AI ---
        # Если ты используешь g4f или OpenAI, вставь код сюда.
        # Пока сделаем простую заглушку, чтобы проверить связь:
        
        import g4f # Попробуем использовать бесплатный AI
        
        response = g4f.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            stream=False
        )
        
        # Пытаемся вернуть JSON, который ждет твой frontend
        return jsonify({
            "choices": [{
                "message": {
                    "content": response
                }
            }]
        })

    except Exception as e:
        print(f"Ошибка AI: {e}")
        return jsonify({"error": str(e)}), 500

# --- ЛОГИКА TELEGRAM BOTA ---

@bot.message_handler(commands=['start'])
def start(message):
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
        markup = telebot.types.InlineKeyboardMarkup()
        # Вставь сюда URL своего приложения на Render или t.me ссылку
        app_url = "https://t.me/Finans_Neyro_bot/app" 
        btn = telebot.types.InlineKeyboardButton("🚀 Открыть НейроСчет", web_app=telebot.types.WebAppInfo(url="https://finance-tg-app.onrender.com"))
        markup.add(btn)
        bot.send_message(message.chat.id, "Добро пожаловать! Нажми кнопку ниже:", reply_markup=markup)

@bot.pre_checkout_query_handler(func=lambda query: True)
def checkout(query):
    bot.answer_pre_checkout_query(query.id, ok=True)

@bot.message_handler(content_types=['successful_payment'])
def success(message):
    user_id = message.from_user.id
    new_date = (datetime.now() + timedelta(days=30)).isoformat()
    try:
        supabase.table("subscriptions").upsert({"user_id": user_id, "expires_at": new_date}).execute()
        bot.send_message(message.chat.id, "✅ Подписка продлена! Перезапустите приложение.")
    except Exception as e:
        bot.send_message(message.chat.id, "Ошибка базы данных, но оплата прошла.")

# --- ЗАПУСК ---

def run_flask():
    # Render требует слушать порт 10000 (или из env)
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

if __name__ == "__main__":
    # 1. Сбрасываем вебхук (Лечит ошибку Network unreachable / conflict)
    try:
        print("Удаляю вебхук...")
        bot.remove_webhook()
        time.sleep(1)
    except Exception as e:
        print(f"Ошибка при удалении вебхука (не страшно): {e}")

    # 2. Запускаем сервер Flask в отдельном потоке (Для AI и Render)
    t = threading.Thread(target=run_flask)
    t.daemon = True
    t.start()

    # 3. Запускаем бота (infinity_polling лучше обычного polling)
    print("Запускаю бота...")
    bot.infinity_polling(skip_pending=True)
