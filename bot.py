import os
import json
import requests
from flask import Flask, request, jsonify
from flask_cors import CORS

# --- ENV ---
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")

app = Flask(__name__)
CORS(app)

@app.route("/chat", methods=["POST"])
def chat_ai():
    try:
        data = request.json or {}
        prompt = data.get("prompt", "")
        history = data.get("history", [])

        system_prompt = """
Ты — умный личный финансовый ассистент.

ТЕБЕ ПЕРЕДАЮТ history — МАССИВ транзакций пользователя.

ФОРМАТ history:
- t: "exp" | "inc"
- c: категория (строка)
- s: сумма (число)
- n: описание
- d: дата YYYY-MM-DD

СТРОГИЕ ПРАВИЛА:

1. ЕСЛИ пользователь описывает ФАКТ:
   "купил", "заправил", "получил", "зарплата", "дивиденды"

➡️ ВЕРНИ ТОЛЬКО JSON:
{
  "action": "add",
  "type": "exp | inc",
  "category": "строка",
  "amount": число,
  "note": "кратко"
}

❌ НИКАКОГО текста вместе с JSON

2. ЕСЛИ пользователь просит:
   анализ, итоги, советы, период, статистику

➡️ ВЕРНИ:
{
  "action": "chat",
  "text": "подробный анализ на основе history"
}

❌ ЗАПРЕЩЕНО добавлять транзакции при анализе
❌ ЗАПРЕЩЕНО возвращать JSON при анализе

3. Ты ОБЯЗАН:
- использовать ВСЮ history
- считать суммы
- фильтровать по датам
- находить проблемные категории
- давать конкретные советы
"""

        payload = {
            "model": "google/gemini-2.0-flash-001",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
                {
                    "role": "assistant",
                    "content": "История транзакций:\n" + json.dumps(
                        history, ensure_ascii=False
                    )
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

        return jsonify(r.json())

    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

