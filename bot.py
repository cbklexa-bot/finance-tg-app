import os, time, threading, telebot, requests, json, re
from flask import Flask, request, jsonify
from flask_cors import CORS
from supabase import create_client, Client
from datetime import datetime, timedelta

# --- НАСТРОЙКИ ---
TOKEN = os.environ.get('BOT_TOKEN')
URL = os.environ.get('SUPABASE_URL')
KEY = os.environ.get('SUPABASE_KEY')
OR_KEY = os.environ.get('OPENROUTER_API_KEY') # Ключ OpenRouter для DeepSeek

bot = telebot.TeleBot(TOKEN)
supabase: Client = create_client(URL, KEY)

app = Flask(__name__)
CORS(app) # Разрешаем запросы с вашего домена .pages.dev

# --- ЛОГИКА AI (DeepSeek) ---
@app.route('/chat', methods=['POST'])
def chat_ai():
    try:
        data = request.json
        prompt = data.get('prompt', '')
        
        # Инструкция для ИИ, чтобы он понимал категории доходов
        system_instruction = f"""
        Ты финансовый ассистент. Сегодня: {datetime.now().strftime("%Y-%m-%d")}.
        Твоя задача: проанализировать текст и вернуть JSON.
        
        КАТЕГОРИИ ДОХОДОВ (t: "inc"): зарплата, инвест, подарок.
        КАТЕГОРИИ РАСХОДОВ (t: "exp"): продукты, авто, жильё, шопинг, аптека, отдых.
        Если категория не подходит, используй "прочее".

        ВЕРНИ СТРОГО JSON:
        {{"action": "add", "amount": число, "category": "название", "type": "inc/exp", "note": "описание"}}
        """

        headers = {"Authorization": f"Bearer {OR_KEY}", "Content-Type": "application/json"}
        payload = {
            "model": "deepseek/deepseek-chat", # Используем DeepSeek V3
            "messages": [
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.1
        }
        
        resp = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload, timeout=60)
        ai_content = resp.json()['choices'][0]['message']['content']
        
        # Очищаем ответ от возможных Markdown-тегов
        clean_json = re.sub(r"```json|```", "", ai_content).strip()
        
        return jsonify({"choices": [{"message": {"content": clean_json}}]})
    except Exception as e:
        print(f"AI Error: {e}")
        return jsonify({"error": str(e)}), 500

# --- ВАША ЛОГИКА ТЕЛЕГРАМ БОТА (Платежи) ---
@bot.message_handler(commands=['start'])
def start(message):
    if "pay" in message.text:
        bot.send_invoice(
            message.chat.id, "НейроСчет: Подписка", "Доступ на 30 дней", "month_sub",
            "", "XTR", [telebot.types.LabeledPrice("Активировать", 100)], start_parameter="pay"
        )
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

# --- ЗАПУСК ---
def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    bot.polling(none_stop=True)
