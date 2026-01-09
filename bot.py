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

        # 1. СБОР ДАННЫХ И ТЕКУЩАЯ ДАТА
        now = datetime.now()
        current_date_str = now.strftime("%Y-%m-%d")
        
        stats_summary = "Данных нет."
        history_text = "История операций пуста."
        if user_id:
            try:
                # Тянем 50 последних транзакций
                res = supabase.table("transactions").select("*").eq("user_id", user_id).order("created_at", desc=True).limit(50).execute()
                if res.data:
                    inc = sum(t['amount'] for t in res.data if t['type'] == 'income')
                    exp = sum(t['amount'] for t in res.data if t['type'] == 'expense')
                    stats_summary = f"БАЛАНС: {inc - exp} | ДОХОД: {inc} | РАСХОД: {exp}"
                    lines = [f"- {t['created_at'][:10]}: {t['type']} | {t['category']} | {t['amount']} руб. ({t.get('description','')})" for t in res.data]
                    history_text = "\n".join(lines)
            except Exception as e: 
                print(f"DB Error: {e}")

        # 2. ИНСТРУКЦИЯ (Указываем дату, чтобы он считал январь верно)
        system_instruction = f"""
        Ты — DeepSeek-V3, личный финансовый эксперт. Сегодняшняя дата: {current_date_str}.
        
        ТВОЯ БАЗА ДАННЫХ:
        {stats_summary}
        
        СПИСОК ОПЕРАЦИЙ:
        {history_text}

        ПРАВИЛА:
        1. Если спрашивают за январь, смотри только на даты 2026-01-XX. 
        2. Считай суммы СТРОГО по списку выше. Не придумывай цифры.
        3. Категории расходов: продукты, авто, жильё, шопинг, аптека, подарки, отдых, прочее.
        4. Категории доходов: зарплата, инвест, подарок, прочее.
        5. Если нужно записать операцию, используй формат:
        [JSON_DATA]{{"amount": число, "category": "категория", "type": "expense|income", "description": "описание"}}[/JSON_DATA]
        """

        # 3. СТРОГИЙ ЗАПРОС (Используем провайдера DeepSeek напрямую)
        headers = {
            "Authorization": f"Bearer {OR_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://finance-tg-app.onrender.com"
        }
        
        payload = {
            # Используем конкретную версию, чтобы избежать "умной" маршрутизации
            "model": "deepseek/deepseek-chat",
            "messages": [
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0, # Ноль делает его "калькулятором", а не "сказочником"
            "top_p": 1,
            "provider": {
                "allow_fallbacks": False # Жесткий запрет на Gemini
            }
        }
        
        response_raw = requests.post(
            "https://openrouter.ai/api/v1/chat/completions", 
            headers=headers, 
            json=payload, 
            timeout=60
        )
        
        response = response_raw.json()
        
        # Если DeepSeek не ответил, мы НЕ идем к Gemini, а выдаем ошибку
        if 'choices' not in response:
            return jsonify({"choices": [{"message": {"content": "DeepSeek сейчас перегружен. Я заблокировал переход на Gemini, чтобы не давать вам ложных цифр. Попробуйте через 30 секунд."}}]})
            
        ai_message = response['choices'][0]['message']['content']

        # 4. АВТОЗАПИСЬ (Без изменений)
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
        print(f"Global Error: {e}")
        return jsonify({"error": str(e)}), 500

@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(message.chat.id, " Привет! Я твой финансовый аналитик.")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    threading.Thread(target=lambda: app.run(host="0.0.0.0", port=port), daemon=True).start()
    bot.infinity_polling()
