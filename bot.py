import os
import time
import json
import re
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import requests
from supabase import create_client, Client

# ================== НАСТРОЙКИ ==================
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

app = Flask(__name__, static_folder='.')
CORS(app)

# ================== FRONT ==================
@app.route("/")
def index():
    return send_from_directory('.', 'index.html')

# ================== AI CHAT ==================
@app.route("/chat", methods=["POST"])
def chat():
    try:
        body = request.json or {}
        prompt = body.get("prompt", "")
        history = body.get("history", [])
        stats = body.get("stats", {})

        system_prompt = f"""
Ты — ЛИЧНЫЙ ФИНАНСОВЫЙ АССИСТЕНТ пользователя.

ТЕБЕ ПЕРЕДАЮТ:
- history: массив транзакций (для контекста)
- stats: ГОТОВЫЕ ПОСЧИТАННЫЕ ДАННЫЕ

СТРОГО ЗАПРЕЩЕНО:
❌ считать суммы
❌ пересчитывать категории
❌ угадывать цифры

РАЗРЕШЕНО:
✅ объяснять
✅ анализировать
✅ давать советы
✅ делать выводы ТОЛЬКО по stats

ФОРМАТЫ ОТВЕТА:

1️⃣ Добавление транзакции (ТОЛЬКО если пользователь явно описал факт):
{{
  "action":"add",
  "type":"exp|inc",
  "category":"строка",
  "amount":число,
  "note":"описание"
}}

2️⃣ Анализ / вопрос:
{{
  "action":"chat",
  "text":"человеческий анализ + советы"
}}

Если stats пуст — скажи, что анализ невозможен.
"""

        payload = {
            "model": "deepseek/deepseek-chat",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
                {
                    "role": "assistant",
                    "content": f"STATS:\n{json.dumps(stats, ensure_ascii=False)}"
                }
            ],
            "temperature": 0.2
        }

        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json"
        }

        r = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=60
        )

        data = r.json()
        content = data["choices"][0]["message"]["content"]

        return jsonify({
            "choices": [
                {"message": {"content": content}}
            ]
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)


