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

# --- ЛОГИКА AI (DeepSeek) ---
@app.route('/chat', methods=['POST'])
def chat_ai():
    try:
        data = request.json
        prompt = data.get('prompt', '')
        # Получаем историю транзакций из фронтенда
        history_data = data.get('history', [])
        
        # Форматируем историю для ИИ, чтобы он мог её прочитать
        history_str = ""
        if history_data:
            for item in history_data[:50]: # Передаем последние 50 записей для анализа
                type_label = "Доход" if item.get('t') == 'inc' else "Расход"
                history_str += f"- {item.get('d')}: {type_label} {item.get('s')}р ({item.get('n')})\n"
        else:
            history_str = "История пуста."

        # ОБНОВЛЕННАЯ ИНСТРУКЦИЯ
        system_instruction = f"""
        Ты финансовый ассистент и аналитик. Сегодня: {datetime.now().strftime("%Y-%m-%d")}.
        
        ИСТОРИЯ ОПЕРАЦИЙ ПОЛЬЗОВАТЕЛЯ:
        {history_str}
        
        ТВОЯ ЗАДАЧА:
        1. Если пользователь хочет ЗАПИСАТЬ (например: "купил хлеб 100"): 
           Верни JSON: {{"action": "add", "amount": число, "category": "название", "type": "inc/exp", "note": "описание"}}
        
        2. Если пользователь спрашивает АНАЛИЗ, СОВЕТ или ВОПРОС (например: "сколько я потратил?", "дай совет"):
           Верни JSON: {{"action": "chat", "text": "Твой подробный ответ на основе истории операций выше"}}
           
        ПРАВИЛА:
        - КАТЕГОРИИ: зарплата, инвест, подарок, продукты, авто, жильё, шопинг, аптека, отдых, прочее.
        - Если в сообщении НЕТ суммы для записи, всегда выбирай action: "chat".
        - Для анализа используй только те данные, которые видишь в истории выше.
        """

        headers = {"Authorization": f"Bearer {OR_KEY}", "Content-Type": "application/json"}
        payload = {
            "model": "deepseek/deepseek-chat",
            "messages": [
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.2 # Немного повысили для более "человечных" советов
        }
        
        resp = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload, timeout=60)
        ai_content = resp.json()['choices'][0]['message']['content']
        
        clean_json = re.sub(r"```json|```", "", ai_content).strip()
        
        return jsonify({"choices": [{"message": {"content": clean_json}}]})
    except Exception as e:
        print(f"AI Error: {e}")
        return jsonify({"error": str(e)}), 500

# --- ЛОГИКА ТЕЛЕГРАМ БОТА ---
@bot.message_handler(commands=['start'])
def start(message):
    if "pay" in message.text:
        bot.send_invoice(message.chat.id, "НейроСчет: Подписка", "Доступ на 30 дней", "month_sub", "", "XTR", [telebot.types.LabeledPrice("Активировать", 100)], start_parameter="pay")
    else:
        bot.send_message(message.chat.id, "Добро пожаловать в НейроСчет!")

@bot.pre_checkout_query_handler(func=lambda query: True)
def checkout(query):
    bot.answer_pre_checkout_query(query.id, ok=True)

@bot.message_handler(content_types=['successful_payment'])
def success(message):
    new_date = (datetime.now() + timedelta(days=30)).isoformat()
    supabase.table("subscriptions").upsert({"user_id": message.from_user.id, "expires_at": new_date}).execute()
    bot.send_message(message.chat.id, "✅ Подписка продлена!")

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    bot.polling(none_stop=True)
