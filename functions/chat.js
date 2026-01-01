export async function onRequestPost({ request, env }) {
  try {
    const { prompt, history } = await request.json();
    const today = new Date().toLocaleDateString('ru-RU');

    // Берем последние 40 транзакций для контекста
    const context = history && history.length > 0 
      ? JSON.stringify(history.slice(0, 40)) 
      : "Транзакций пока нет";

    const response = await fetch("https://openrouter.ai/api/v1/chat/completions", {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${env.OPENROUTER_API_KEY}`,
        "Content-Type": "application/json",
        "HTTP-Referer": "https://finance-tg-app.pages.dev"
      },
      body: JSON.stringify({
        model: "google/gemini-2.0-flash-001",
        messages: [
          {
            role: "system",
            content: `Ты — элитный финансовый аналитик. 
            Сегодня: ${today}. 
            Данные пользователя: ${context}.

            ТВОИ ЗАДАЧИ:
            1. ЕСЛИ ЭТО ТРАТА/ДОХОД: Верни ТОЛЬКО JSON: {"action":"add","type":"exp или inc","category":"emoji","amount":число,"note":"..."}
            2. ЕСЛИ ЭТО ВОПРОС ПО ИСТОРИИ (Анализ): Сделай глубокий расчет. Считай суммы, сравнивай категории. Ответ давай в JSON: {"action":"chat","text":"Твой детальный ответ"}
            3. ЕСЛИ ЭТО ОБЩЕНИЕ: Отвечай дружелюбно в JSON: {"action":"chat","text":"..."}

            ВАЖНО: Всегда отвечай СТРОГО в формате JSON. Не пиши лишних слов до или после JSON.`
          },
          { role: "user", content: prompt }
        ]
      })
    });

    const data = await response.json();
    return new Response(JSON.stringify(data), { headers: { "Content-Type": "application/json" } });
  } catch (e) {
    return new Response(JSON.stringify({ error: e.message }), { status: 500 });
  }
}







