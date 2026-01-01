export async function onRequestPost({ request, env }) {
  try {
    const { prompt, history } = await request.json();

    // Превращаем историю в читаемый для ИИ текст
    const historyContext = history && history.length > 0 
      ? `История последних транзакций: ${JSON.stringify(history)}`
      : "История транзакций пока пуста.";

    const response = await fetch("https://openrouter.ai/api/v1/chat/completions", {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${env.OPENROUTER_API_KEY}`,
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        model: "google/gemini-2.0-flash-001", // Самая умная и быстрая модель для анализа
        messages: [
          {
            role: "system",
            content: `Ты — экспертный финансовый аналитик премиум-класса. 
            Твоя задача: помогать пользователю управлять личными финансами.

            ДАННЫЕ ПОЛЬЗОВАТЕЛЯ:
            ${historyContext}

            ТВОИ ВОЗМОЖНОСТИ:
            1. ЗАПИСЬ: Если видишь трату/доход, верни JSON: {"action":"add","type":"exp/inc","category":"emoji","amount":0,"note":"..."}
            2. АНАЛИЗ: Если пользователь просит анализ ("Сколько я потратил?", "На чем сэкономить?", "Сделай отчет"), проведи глубокий расчет по предоставленной истории.
            3. СОВЕТЫ: Давай рекомендации по финансовой грамотности на основе реальных трат.

            ФОРМАТ ОТВЕТА:
            - Если это запись транзакции: ТОЛЬКО JSON {"action":"add",...}
            - Если это анализ/вопрос: верни JSON {"action":"chat","text":"Твой детальный анализ с цифрами и советами"}.
            - В текстовых ответах используй абзацы и эмодзи для читабельности.`
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





