export async function onRequestPost(context) {
  const { request, env } = context;
  const body = await request.json();

  // Это инструкция для ИИ
  const systemPrompt = `Ты — финансовый помощник. Ты анализируешь текст и возвращаешь ТОЛЬКО JSON.
  Формат ответа:
  1. Если это трата/доход: {"action": "add", "type": "exp", "amount": 500, "category": "🍔", "note": "Обед"}
  2. Если это вопрос/чат: {"action": "chat", "text": "Твой ответ пользователю"}
  
  Доступные иконки категорий: 🛒, 🚗, 🍔, 💊, 🏠, 🎁, 🎮, 👕, 🍕, 💰.
  Если категория неясна, используй 📦.`;

  const response = await fetch("https://openrouter.ai/api/v1/chat/completions", {
    method: "POST",
    headers: {
      "Authorization": `Bearer ${env.OPENROUTER_API_KEY}`,
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      model: "deepseek/deepseek-chat", // Можно поменять на google/gemini-flash-1.5 для скорости
      messages: [
        { role: "system", content: systemPrompt },
        { role: "user", content: body.prompt }
      ],
      response_format: { type: "json_object" } 
    })
  });

  const data = await response.json();
  return new Response(JSON.stringify(data), {
    headers: { 'Content-Type': 'application/json' }
  });
}
