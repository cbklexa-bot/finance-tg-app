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

        # 1. ТОЧНЫЙ РАСЧЕТ БАЛАНСА ИЗ БАЗЫ
        stats_info = "Данных о транзакциях пока нет."
        if user_id:
            try:
                res = supabase.table("transactions").select("*").eq("user_id", user_id).execute()
                if res.data:
                    income = sum(t['amount'] for t in res.data if t['type'] == 'income')
                    expense = sum(t['amount'] for t in res.data if t['type'] == 'expense')
                    balance = income - expense
                    stats_info = f"ТОЧНЫЙ ТЕКУЩИЙ БАЛАНС: {balance}. Общий доход: {income}. Общий расход: {expense}. Всего операций: {len(res.data)}."
            except Exception as e:
                print(f"Ошибка БД: {e}")

        # 2. ИНСТРУКЦИЯ ДЛЯ ЭКСПЕРТА
        system_instruction = f"""
        Ты — финансовый эксперт-консультант "НейроСчет". 
        Твоя база знаний по текущему пользователю: {stats_info}
        
        ТВОИ ЗАДАЧИ:
        1. Если спрашивают баланс — называй число из блока "ТОЧНЫЙ ТЕКУЩИЙ БАЛАНС". Не выдумывай свое!
        2. Категоризируй траты: 
           - Авто (бензин, мойка, ремонт, запчасти, шиномонтаж, страховка)
           - Жилье (коммуналка, свет, вода, интернет)
           - Продукты (еда, супермаркет)
           - Разное (аптека, кафе, кофе)
        3. Если нужно записать расход/доход, ОБЯЗАТЕЛЬНО добавь в конец сообщения:
        [JSON_DATA]{{"amount": число, "category": "категория", "type": "expense или income", "description": "описание"}}[/JSON_DATA]
        """

        # 3. ЗАПРОС К OPENROUTER
        headers = {"Authorization": f"Bearer {OR_KEY}", "Content-Type": "application/json"}
        payload = {
            "model": "deepseek/deepseek-chat",
            "messages": [
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": prompt}
            ],
            "route": "fallback"
        }
        
        response = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload, timeout=30).json()
        
        if 'choices' not in response:
            return jsonify({"error": "AI Error"}), 500
            
        ai_message = response['choices'][0]['message']['content']

        # 4. АВТОМАТИЧЕСКАЯ ЗАПИСЬ В SUPABASE
        if "[JSON_DATA]" in ai_message:
            match = re.search(r"\[JSON_DATA\](.*?)\[/JSON_DATA\]", ai_message)
            if match and user_id:
                try:
                    tx = json.loads(match.group(1))
                    supabase.table("transactions").insert({
                        "user_id": user_id,
                        "amount": float(tx['amount']),
                        "category": tx['category'],
                        "type": tx['type'],
                        "description": tx.get('description', '')
                    }).execute()
                    ai_message = ai_message.replace(match.group(0), "").strip()
                except Exception as db_e:
                    print(f"Ошибка вставки в БД: {db_e}")

        return jsonify({"choices": [{"message": {"content": ai_message}}]})

    except Exception as e:
        print(f"Global Error: {e}")
        return jsonify({"error": str(e)}), 500

# --- КОД БОТА БЕЗ КНОПОК ---
@bot.message_handler(commands=['start'])
def start(message):
    welcome_text = (
        "🦁 Привет! Я твой финансовый эксперт.\n\n"
        "Я помогу тебе вести учет доходов и расходов. Просто пиши мне в чат сообщения в свободном стиле, "
        "например: 'потратил на бензин 2000' или 'купил хлеб и молоко на 300'.\n\n"
        "Я сам определю категорию и запишу всё в базу. Также ты можешь спросить меня о текущем балансе или анализе трат."
    )
    bot.send_message(message.chat.id, welcome_text)

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    while True:
        try:
            bot.infinity_polling(skip_pending=True)
        except:
            time.sleep(5)
