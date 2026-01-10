import os, time, threading, telebot, requests, json, re
from flask import Flask, request, jsonify
from flask_cors import CORS
from supabase import create_client, Client
from datetime import datetime, timedelta

# --- НАСТРОЙКИ ---
TOKEN = os.environ.get('BOT_TOKEN')
URL = os.environ.get('SUPABASE_URL')
KEY = os.environ.get('SUPABASE_KEY')
OR_KEY = os.environ.get('OPENROUTER_API_KEY')

bot = telebot.TeleBot(TOKEN)
supabase: Client = create_client(URL, KEY)

app = Flask(__name__)
CORS(app)

# Хелсчек для Render
@app.route('/')
def health():
    return "Бот и Сервер запущены", 200

@app.route('/chat', methods=['POST'])
def chat_ai():
    try:
        data = request.json
        prompt = data.get('prompt', '')
        history_data = data.get('history', [])
        
        history_str = ""
        if history_data:
            for item in history_data[:40]:
                t_type = "Доход" if item.get('t') == 'inc' else "Расход"
                history_str += f"- {item.get('d')}: {t_type} {item.get('s')}р ({item.get('n')})\n"
        else:
            history_str = "История операций пуста."

        system_instruction = f"""
        Ты финансовый ассистент НейроСчет. Сегодня: {datetime.now().strftime("%Y-%m-%d")}.
        ИСТОРИЯ ОПЕРАЦИЙ:
        {history_str}
        ТВОЯ ЗАДАЧА:
        1. Если пользователь хочет ЗАПИСАТЬ:
           Верни СТРОГО JSON: {{"action": "add", "amount": число, "category": "название", "type": "inc/exp", "note": "описание"}}
        2. Если пользователь спрашивает АНАЛИЗ, СОВЕТ или ВОПРОС:
           Верни СТРОГО JSON: {{"action": "chat", "text": "Твой ответ"}}
        КАТЕГОРИИ: зарплата, инвест, подарок, продукты, авто, жильё, шопинг, аптека, отдых, прочее.
        """

        headers = {"Authorization": f"Bearer {OR_KEY}", "Content-Type": "application/json"}
        payload = {
            "model": "deepseek/deepseek-chat",
            "messages": [
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.2
        }
        
        resp = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload, timeout=60)
        ai_content = resp.json()['choices'][0]['message']['content']
        
        json_match = re.search(r"\{[\s\S]*?\}", ai_content)
        clean_json = json_match.group(0) if json_match else ai_content
        
        return jsonify({"choices": [{"message": {"content": clean_json}}]})
    except Exception as e:
        print(f"AI Error: {e}")
        return jsonify({"error": str(e)}), 500

# --- ТЕЛЕГРАМ БОТ ---
@bot.message_handler(commands=['start'])
def start(message):
    if "pay" in message.text:
        bot.send_invoice(
            message.chat.id, "НейроСчет: Подписка", "Доступ на 30 дней", "month_sub",
            "", "XTR", [telebot.types.LabeledPrice("Активировать", 100)], start_parameter="pay"
        )
    else:
        bot.send_message(message.chat.id, "✨ Добро пожаловать в НейроСчет! Используйте Mini App для управления финансами.")

@bot.pre_checkout_query_handler(func=lambda query: True)
def checkout(query):
    bot.answer_pre_checkout_query(query.id, ok=True)

@bot.message_handler(content_types=['successful_payment'])
def success(message):
    new_date = (datetime.now() + timedelta(days=30)).isoformat()
    try:
        supabase.table("subscriptions").upsert({"user_id": message.from_user.id, "expires_at": new_date}).execute()
        bot.send_message(message.chat.id, "✅ Оплата прошла! Доступ продлен на 30 дней.")
    except Exception as e:
        print(f"Supabase error: {e}")

# --- ПРАВИЛЬНЫЙ ЗАПУСК ---

def run_bot():
    print("Запуск бота...")
    bot.infinity_polling(timeout=20, long_polling_timeout=10)

if __name__ == "__main__":
    # 1. Запускаем бота в отдельном потоке
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()

    # 2. Запускаем Flask в основном потоке (обязательно для Render)
    port = int(os.environ.get("PORT", 10000))
    print(f"Flask сервер запущен на порту {port}")
    app.run(host="0.0.0.0", port=port)
