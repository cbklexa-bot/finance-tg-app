import os, time, threading, telebot, requests, json, re
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from supabase import create_client, Client
from datetime import datetime

# Настройки (убедись, что переменные в Render прописаны)
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
        prompt = data.get('prompt', '')
        user_id = str(data.get('user_id', ''))

        # 1. ПОЛУЧАЕМ ЧИСТУЮ ИСТОРИЮ ИЗ БАЗЫ
        history_text = "История пуста."
        res = supabase.table("finance").select("data").eq("user_id", user_id).order("created_at", desc=True).limit(40).execute()
        
        if res.data:
            items = []
            for row in res.data:
                d = row['data']
                # Формат для ИИ: Дата | Тип | Сумма | Категория | Описание
                type_name = "Доход" if d.get('t') == 'inc' else "Расход"
                items.append(f"{d.get('d')}: {type_name} {d.get('s')} руб. [{d.get('c')}] {d.get('n')}")
            history_text = "\n".join(items)

        # 2. ЖЕСТКАЯ СИСТЕМНАЯ ИНСТРУКЦИЯ
        system_msg = f"""Ты — эксперт по личным финансам. Сегодня {datetime.now().strftime('%Y-%m-%d')}.
У тебя есть доступ к истории операций пользователя ниже. Твоя цель: помогать записывать траты и анализировать их.

ИСТОРИЯ ОПЕРАЦИЙ:
{history_text}

ПРАВИЛА ОТВЕТА:
1. Если пользователь хочет ЗАПИСАТЬ операцию, верни текст подтверждения и строго в конце добавь блок:
[JSON]{{"s": сумма_числом, "c": "иконка_категории", "t": "exp_или_inc", "n": "описание"}}[/JSON]
Иконки: 🛒(продукты), 🚗(авто), 🏠(жилье), 🛍️(шопинг), 💊(аптека), 🎭(отдых), 💵(доход), 📦(прочее).

2. Если пользователь спрашивает АНАЛИЗ (например, "сколько я потратил на еду?"), ТЫ ДОЛЖЕН САМ СЛОЖИТЬ ЦИФРЫ ИЗ ИСТОРИИ ВЫШЕ И ДАТЬ ТОЧНЫЙ ОТВЕТ. Не придумывай цифры!
3. Отвечай всегда по-русски, кратко и дружелюбно."""

        # 3. ЗАПРОС К DEEPSEEK (через OpenRouter)
        resp = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {OR_KEY}", "Content-Type": "application/json"},
            json={
                "model": "deepseek/deepseek-chat",
                "messages": [
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.1 # Минимум фантазии, максимум точности
            }
        )
        ai_raw_content = resp.json()['choices'][0]['message']['content']

        # 4. ЛОГИКА ЗАПИСИ В SUPABASE
        if "[JSON]" in ai_raw_content:
            json_match = re.search(r"\[JSON\](.*?)\[/JSON\]", ai_raw_content)
            if json_match:
                tx_data = json.loads(json_match.group(1))
                # Дополняем техническими полями
                tx_data['d'] = datetime.now().strftime("%Y-%m-%d")
                tx_data['id'] = int(time.time() * 1000)

                # Записываем в базу
                supabase.table("finance").insert({"user_id": user_id, "data": tx_data}).execute()
                
                # Удаляем тех. инфо из сообщения для юзера
                ai_raw_content = ai_raw_content.replace(json_match.group(0), "").strip()

        return jsonify({"content": ai_raw_content})

    except Exception as e:
        print(f"ERROR: {e}")
        return jsonify({"content": "Произошла ошибка в обработке запроса."}), 500

# Запуск
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    threading.Thread(target=lambda: bot.polling(none_stop=True), daemon=True).start()
    app.run(host="0.0.0.0", port=port)
