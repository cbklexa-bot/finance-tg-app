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

        # 1. СБОР ИСТОРИИ ДЛЯ ГЛУБОКОГО АНАЛИЗА
        stats_summary = "Данных нет."
        history_text = "История операций пуста."
        if user_id:
            try:
                res = supabase.table("transactions").select("*").eq("user_id", user_id).order("created_at", desc=True).limit(50).execute()
                if res.data:
                    inc = sum(t['amount'] for t in res.data if t['type'] == 'income')
                    exp = sum(t['amount'] for t in res.data if t['type'] == 'expense')
                    stats_summary = f"БАЛАНС: {inc - exp} | ДОХОД: {inc} | РАСХОД: {exp}"
                    lines = [f"- {t['created_at'][:10]}: {t['type']} | {t['category']} | {t['amount']} руб. ({t.get('description','')})" for t in res.data]
                    history_text = "\n".join(lines)
            except Exception as e: print(f"DB Error: {e}")

        # 2. ИНСТРУКЦИЯ С ТВОИМИ КАТЕГОРИЯМИ
        system_instruction = f"""
        Ты — DeepSeek-V3, личный финансовый консультант. Твоя задача — вести учет и анализировать историю.

        ДАННЫЕ ПОЛЬЗОВАТЕЛЯ:
        {stats_summary}
        
        ПОСЛЕДНИЕ ОПЕРАЦИИ:
        {history_text}

        ТВОИ КАТЕГОРИИ РАСХОДОВ:
        - продукты, авто, жильё, шопинг, аптека, подарки, отдых, прочее.

        ТВОИ КАТЕГОРИИ ДОХОДОВ:
        - зарплата, инвест, подарок, прочее.

        ТВОИ ПРАВИЛА:
        1. Распознавай тип (expense/income) и категорию автоматически.
        2. Если нужно записать, ОБЯЗАТЕЛЬНО используй формат:
        [JSON_DATA]{{"amount": число, "category": "название_категории", "type": "expense|income", "description": "описание"}}[/JSON_DATA]
        3. Анализируй историю: если в категории "шопинг" много трат, посоветуй быть экономнее.
        4. Отвечай кратко, но профессионально.
        """

        # 3. ЗАПРОС К OPENROUTER (DEEPSEEK-V3)
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
            ],
            "temperature": 0.1
        }
        
        response = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload, timeout=45).json()
        ai_message = response['choices'][0]['message']['content']

        # 4. АВТОЗАПИСЬ В БАЗУ
        if "[JSON_DATA]" in ai_message:
            match = re.search(r"\[JSON_DATA\](.*?)\[/JSON_DATA\]", ai_message)
            if match and user_id:
                try:
                    tx = json.loads(match.group(1))
                    supabase.table("transactions").insert({
                        "user_id": user_id,
                        "amount": float(tx['amount']),
                        "category": tx['category'].lower(),
                        "type": tx['type'],
                        "description": tx.get('description', '')
                    }).execute()
                    ai_message = ai_message.replace(match.group(0), "").strip()
                except: pass

        return jsonify({"choices": [{"message": {"content": ai_message}}]})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(message.chat.id, "🦁 Привет! Твой персональный эксперт на базе DeepSeek-V3 готов к работе.'.")

if __name__ == "__main__":
    threading.Thread(target=lambda: app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000))), daemon=True).start()
    bot.infinity_polling()
