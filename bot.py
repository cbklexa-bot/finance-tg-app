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
from datetime import datetime

# --- НАСТРОЙКИ ---
TOKEN = os.environ.get('BOT_TOKEN')
URL = os.environ.get('SUPABASE_URL')
KEY = os.environ.get('SUPABASE_KEY')
OR_KEY = os.environ.get('OPENROUTER_API_KEY')

# Инициализация
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
        prompt = data.get('prompt') or ""
        user_id = data.get('user_id')

        # 1. СБОР ИСТОРИИ
        history_text = "История операций пуста."
        if user_id:
            try:
                res = supabase.table("finance").select("data").eq("user_id", str(user_id)).order("created_at", desc=True).limit(50).execute()
                if res.data:
                    lines = []
                    for item in res.data:
                        d = item.get('data', {})
                        if isinstance(d, str): d = json.loads(d)
                        t_type = "Расход" if d.get('t') == 'exp' else "Доход"
                        lines.append(f"- {d.get('d')}: {t_type} {d.get('c')} {d.get('s')}р. ({d.get('n')})")
                    history_text = "\n".join(lines)
            except Exception as e:
                print(f"DB Read Error: {e}")

        # 2. ИНСТРУКЦИЯ
        system_instruction = f"""
        Ты финансовый ассистент. Сегодня: {datetime.now().strftime("%Y-%m-%d")}.
        Твой формат записи: [JSON_DATA]{{"s": сумма, "c": "иконка", "t": "exp|inc", "n": "название"}}[/JSON_DATA]

        ИСТОРИЯ ОПЕРАЦИЙ:
        {history_text}

        ПРАВИЛА:
        1. Если просят записать — ответь коротко и дай JSON.
        2. Если просят анализ — считай по истории.
        3. Категории: 🛒 Продукты, 🚗 Авто, 🏠 Жильё, 🛍️ Шопинг, 💊 Аптека, 🎭 Отдых, 🎁 Подарки, 💵 Зарплата, 📈 Инвест, 📦 Прочее.
        """

        # 3. ЗАПРОС К OPENROUTER
        headers = {"Authorization": f"Bearer {OR_KEY}", "Content-Type": "application/json"}
        payload = {
            "model": "deepseek/deepseek-chat",
            "messages": [
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.2
        }
        
        response_raw = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload, timeout=60)
        ai_message = response_raw.json()['choices'][0]['message']['content']

        # 4. СОХРАНЕНИЕ В БАЗУ
        if "[JSON_DATA]" in ai_message:
            match = re.search(r"\[JSON_DATA\]([\s\S]*?)\[/JSON_DATA\]", ai_message)
            if match and user_id:
                try:
                    tx = json.loads(match.group(1).strip())
                    tx['d'] = datetime.now().strftime("%Y-%m-%d")
                    tx['id'] = int(time.time() * 1000)

                    supabase.table("finance").insert({
                        "user_id": str(user_id),
                        "data": tx
                    }).execute()
                    
                    ai_message = re.sub(r"\[JSON_DATA\].*?\[\/JSON_DATA\]", "", ai_message, flags=re.DOTALL).strip()
                except Exception as e:
                    print(f"Insert error: {e}")

        return jsonify({"choices": [{"message": {"content": ai_message}}]})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- ТЕЛЕГРАМ БОТ ---
@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(message.chat.id, "Привет! Я твой финансовый ИИ-ассистент.")

def run_bot():
    while True:
        try:
            bot.polling(none_stop=True, interval=0, timeout=20)
        except Exception:
            time.sleep(5)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    # Запуск Flask в отдельном потоке
    threading.Thread(target=lambda: app.run(host="0.0.0.0", port=port), daemon=True).start()
    # Запуск Бота
    run_bot()
