import os
import time
import threading
import telebot
import requests
import json
import re
from flask import Flask, request, jsonify, send_from_directory
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

app = Flask(__name__, static_folder='.')
CORS(app)

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/chat', methods=['POST'])
def chat_ai():
    try:
        data = request.json
        prompt = data.get('prompt') or data.get('message') or ""
        user_id = data.get('user_id')

        # 1. Получаем историю транзакций из Supabase для анализа
        history_context = "История пуста."
        if user_id:
            try:
                res = supabase.table("transactions").select("*").eq("user_id", user_id).order("created_at", desc=True).limit(15).execute()
                if res.data:
                    history_context = "\n".join([f"{t['type']}: {t['amount']} на {t['category']} ({t['description']})" for t in res.data])
            except: pass

        # 2. Системная инструкция (Логика эксперта и категоризации)
        system_instruction = f"""
        Ты — финансовый эксперт-консультант "НейроСчет". 
        Твоя задача: анализировать траты и ПОМОГАТЬ записывать их.

        ПРАВИЛА КАТЕГОРИЙ:
        - Авто: бензин, запчасти, мойка, страховка, шиномонтаж, ремонт авто.
        - Жилье: интернет, вода, свет, коммуналка, аренда.
        - Продукты: хлеб, молоко, овощи, еда.
        - Разное: аптека, кофе, развлечения, остальное.

        ЗАПИСЬ ДАННЫХ:
        Если пользователь говорит, что он что-то купил или потратил, ты должен добавить в конец ответа JSON:
        [JSON_DATA]{{"amount": число, "category": "название", "type": "expense", "description": "что именно"}}[/JSON_DATA]

        Контекст пользователя:
        {history_context}
        """

        headers = {
            "Authorization": f"Bearer {OR_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://finance-tg-app.onrender.com"
        }
        
        payload = {
            "model": "deepseek/deepseek-chat",
            "messages": [
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": prompt}
            ]
        }
        
        response = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload, timeout=25).json()
        ai_message = response['choices'][0]['message']['content']

        # 3. Обработка записи в БД, если ИИ выдал JSON
        if "[JSON_DATA]" in ai_message:
            match = re.search(r"\[JSON_DATA\](.*?)\[/JSON_DATA\]", ai_message)
            if match and user_id:
                tx = json.loads(match.group(1))
                supabase.table("transactions").insert({
                    "user_id": user_id,
                    "amount": tx['amount'],
                    "category": tx['category'],
                    "type": tx['type'],
                    "description": tx['description']
                }).execute()
                # Чистим ответ от технического JSON
                ai_message = ai_message.replace(match.group(0), "").strip()

        return jsonify({"choices": [{"message": {"content": ai_message}}]})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- БОТ --- (Остается без изменений)
@bot.message_handler(commands=['start'])
def start(message):
    markup = telebot.types.InlineKeyboardMarkup()
    btn = telebot.types.InlineKeyboardButton("🚀 Открыть НейроСчет", web_app=telebot.types.WebAppInfo(url="https://finance-tg-app.onrender.com"))
    markup.add(btn)
    bot.send_message(message.chat.id, "🦁 Привет! Я твой финансовый эксперт.", reply_markup=markup)

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    while True:
        try: bot.infinity_polling(skip_pending=True)
        except: time.sleep(5)
