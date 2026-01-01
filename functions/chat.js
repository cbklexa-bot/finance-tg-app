export async function onRequestPost({ request, env }) {
  try {
    const { prompt, history } = await request.json();
    const today = new Date().toISOString().split('T')[0];

    // Формируем краткую историю для экономии токенов
    const historyText = history && history.length > 0 
      ? JSON.stringify(history.slice(0, 50)) // Последние 50 транзакций
      : "История пуста";

    const response = await fetch("https://openrouter.ai/api/v1/chat/completions", {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${env.OPENROUTER_API_KEY}`,
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        model: "google/gemini-2.0-flash-001",
        messages: [
          {
            role: "system",
            content: `Ты — продвинутый финансовый аналитик. 
            Сегодняшняя дата: ${today}.
            История транзакций пользователя: ${historyText}.

            ТВОИ ПРАВИЛА:
            1. Если пользователь вводит расход/доход (пр: "купил кофе 200"), верни ТОЛЬКО JSON: 
               {"action":"add", "type":"exp", "category":"☕", "amount":200, "note":"Кофе"}
            
            2. Если пользователь просит анализ (пр: "сколько я потратил?", "сделай отчет"), проанализируй историю и верни JSON: 
               {"action":"chat", "text":"Твой детальный разбор с цифрами и советами"}

            3. Если это просто общение, верни JSON: {"action":"chat", "text":"Приветственный текст"}
            
            ПИШИ ТОЛЬКО ЧИСТЫЙ JSON БЕЗ РАЗМЕТКИ.`
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






