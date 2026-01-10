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
from telebot.apihelper import ApiTelegramException

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

        # 1. СБОР ДАННЫХ (ЧИТАЕМ ИЗ КОЛОНКИ data)
        now = datetime.now()
        current_date_str = now.strftime("%Y-%m-%d")
        
        history_text = "История операций пуста."
        
        if user_id:
            try:
                # Выбираем колонку data, где лежат ваши JSON-объекты
                res = supabase.table("finance").select("data").eq("user_id", str(user_id)).order("created_at", desc=True).limit(40).execute()
                
                if res.data:
                    lines = []
                    for item in res.data:
                        d = item.get('data', {})
                        # Извлекаем данные из вложенного объекта (s - сумма, n - описание, t - тип, c - иконка)
                        type_str = "Доход" if d.get('t') == 'inc' else "Расход"
                        lines.append(f"- {d.get('d')}: {type_str} | {d.get('c')} | {d.get('s')} руб. ({d.get('n')})")
                    history_text = "\n".join(lines)
            except Exception as e: 
                print(f"DB Read Error: {e}")

        # 2. УМНАЯ ИНСТРУКЦИЯ (Подстроена под ваш формат {c, d, n, s, t, id})
        system_instruction = f"""
        Ты — Личный Финансовый Эксперт. Твоя задача: анализировать траты и записывать новые.
        Сегодня: {current_date_str}.

        ТВОИ КАТЕГОРИИ (используй эти иконки):
        🛒 Продукты, 🚗 Авто, 🏠 Жильё, 🛍️ Шопинг, 💊 Аптека, 🎭 Отдых, 🎁 Подарки, 💵 Зарплата, 📈 Инвест, 📦 Прочее.

        ИСТОРИЯ ОПЕРАЦИЙ ПОЛЬЗОВАТЕЛЯ:
        {history_text}

        ПРАВИЛА:
        1. Если пользователь говорит записать расход/доход, ответь коротко и добавь JSON:
        [JSON_DATA]{{"s": число, "c": "иконка", "t": "exp|inc", "n": "описание"}}[/JSON_DATA]
        """

        # 3. ЗАПРОС К OPENROUTER
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
            "temperature": 0.3
        }
        
        response_raw = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload, timeout=60)
        ai_message = response_raw.json()['choices'][0]['message']['content']

        # 4. ОБРАБОТКА JSON И СОХРАНЕНИЕ (В КОЛОНКУ data)
        if "[JSON_DATA]" in ai_message:
            match = re.search(r"\[JSON_DATA\]([\s\S]*?)\[/JSON_DATA\]", ai_message)
            if match and user_id:
                try:
                    tx = json.loads(match.group(1).strip())
                    
                    # Формируем структуру в точности как в твоем примере из базы
                    new_entry = {
                        "c": tx.get('c', '📦'),
                        "d": current_date_str,
                        "n": tx.get('n', ''),
                        "s": float(tx.get('s', 0)),
                        "t": tx.get('t', 'exp'),
                        "id": int(time.time() * 1000)
                    }

                    # Сохраняем в колонку data
                    supabase.table("finance").insert({
                        "user_id": str(user_id),
                        "data": new_entry
                    }).execute()
                    
                    # Убираем технический JSON из ответа
                    ai_message = re.sub(r"\[JSON_DATA\].*?\[/JSON_DATA\]", "", ai_message, flags=re.DOTALL).strip()
                except Exception as e:
                    print(f"Insert error: {e}")

        return jsonify({"choices": [{"message": {"content": ai_message}}]})

    except Exception as e:
        print(f"Global Error: {e}")
        return jsonify({"error": str(e)}), 500

# --- ТЕЛЕГРАМ БОТ ---
@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(message.chat.id, "Привет! Я твой финансовый эксперт. Я вижу твою историю и готов помогать.")

def run_bot():
    bot.remove_webhook()
    time.sleep(1)
    while True:
        try:
            bot.polling(none_stop=True, interval=0, timeout=20)
        except Exception as e:
            time.sleep(5)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    threading.Thread(target=lambda: app.run(host="0.0.0.0", port=port), daemon=True).start()
    run_bot()
