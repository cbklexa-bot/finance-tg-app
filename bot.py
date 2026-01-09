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

        # 1. СБОР ДАННЫХ
        now = datetime.now()
        current_date_str = now.strftime("%Y-%m-%d")
        
        stats_summary = "Данных нет."
        history_text = "История операций пуста."
        
        if user_id:
            try:
                res = supabase.table("transactions").select("*").eq("user_id", user_id).order("created_at", desc=True).limit(50).execute()
                if res.data:
                    inc = sum(t['amount'] for t in res.data if t['type'] == 'income')
                    exp = sum(t['amount'] for t in res.data if t['type'] == 'expense')
                    stats_summary = f"ТЕКУЩИЙ БАЛАНС: {inc - exp} руб. (Всего Доход: {inc}, Всего Расход: {exp})"
                    lines = [f"- {t['created_at'][:10]}: {t['type']} | {t['category']} | {t['amount']} руб. ({t.get('description','')})" for t in res.data]
                    history_text = "\n".join(lines)
            except Exception as e: 
                print(f"DB Error: {e}")

        # 2. УМНАЯ ИНСТРУКЦИЯ (ЛОГИКА ЭКСПЕРТА)
        system_instruction = f"""
        Ты — Личный Финансовый Эксперт-Консультант. Твоя задача: вести учет и помогать пользователю богатеть.
        Сегодня: {current_date_str}.

        ТВОИ КАТЕГОРИИ:
        - РАСХОДЫ: 
          * авто (бензин, мойка, запчасти, шины, масло, страховка, ремонт)
          * жильё (интернет, вода, свет, коммуналка, аренда)
          * продукты (еда, молоко, хлеб, мясо, супермаркеты)
          * аптека (лекарства, витамины)
          * шопинг (одежда, техника)
          * отдых (кафе, кино, прогулки)
          * подарки
          * прочее (кофе, мелочи)
        - ДОХОДЫ: зарплата, инвест, подарок, прочее.

        ТВОИ ПРАВИЛА:
        1. АНАЛИЗ: Если пользователь спрашивает о тратах (например, за январь), считай их СТРОГО по списку операций ниже.
        2. ЗАПИСЬ: Если пользователь говорит что потратил или заработал, ты САМ определяешь категорию из списка выше. 
           Всегда отвечай подтверждением и в конце добавляй JSON:
           [JSON_DATA]{{"amount": число, "category": "категория", "type": "expense|income", "description": "описание"}}[/JSON_DATA]
        3. КОНСУЛЬТАЦИЯ: Давай советы по экономии на основе истории.

        БАЛАНС СЕЙЧАС: {stats_summary}
        ИСТОРИЯ ОПЕРАЦИЙ:
        {history_text}
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
            "temperature": 0.3,
            "provider": { "allow_fallbacks": False }
        }
        
        response_raw = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload, timeout=60)
        response = response_raw.json()
        
        if 'choices' not in response:
            return jsonify({"choices": [{"message": {"content": "Ошибка связи с DeepSeek."}}]})
            
        ai_message = response['choices'][0]['message']['content']

        # 4. ОБРАБОТКА JSON
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
    bot.send_message(message.chat.id, "Привет! Я твой личный финансовый эксперт.")

# --- ЗАЩИТА ОТ 409 CONFLICT И ЗАПУСК ---
def run_bot():
    print("Запуск Telegram бота...")
    # Удаляем вебхук, чтобы работал пуллинг
    bot.remove_webhook()
    time.sleep(1)
    
    while True:
        try:
            bot.polling(none_stop=True, interval=0, timeout=20)
        except ApiTelegramException as e:
            if e.error_code == 409:
                print("Ошибка 409 (Конфликт). Ждем завершения старой сессии...")
                time.sleep(10) # Ждем дольше на Render
            else:
                print(f"Ошибка Telegram API: {e}")
                time.sleep(5)
        except Exception as e:
            print(f"Общая ошибка бота: {e}")
            time.sleep(5)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    # Flask в отдельном потоке
    threading.Thread(target=lambda: app.run(host="0.0.0.0", port=port), daemon=True).start()
    
    # Запуск функции защиты
    run_bot()
