export async function onRequestPost(context) {
  const { request, env } = context;

  // 1. Проверяем наличие ключа в переменных окружения Cloudflare
  if (!env.OPENROUTER_API_KEY) {
    return new Response(
      JSON.stringify({ error: "Критическая ошибка: API ключ не настроен в Cloudflare." }), 
      { status: 500, headers: { 'Content-Type': 'application/json' } }
    );
  }

  try {
    const body = await request.json();

    // 2. Формируем запрос к OpenRouter
    const response = await fetch("https://openrouter.ai/api/v1/chat/completions", {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${env.OPENROUTER_API_KEY}`, // Используем переменную, а не текст!
        "Content-Type": "application/json",
        "HTTP-Referer": "https://pages.cloudflare.com", // Обязательно для OpenRouter
        "X-Title": "Finance TG App"
      },
      body: JSON.stringify({
        model: "deepseek/deepseek-chat",
        messages: [
          { 
            role: "system", 
            content: `Ты — финансовый ассистент. Анализируй текст и возвращай ТОЛЬКО строго валидный JSON.
            Формат ответа:
            1. Если это трата или доход: {"action": "add", "type": "exp", "amount": 500, "category": "🍔", "note": "Обед"}
            2. Если это вопрос или общение: {"action": "chat", "text": "Твой ответ"}
            Категории: 🛒, 🚗, 🍔, 💊, 🏠, 🎁, 🎮, 💰.` 
          },
          { role: "user", content: body.prompt }
        ],
        // Включаем JSON mode, чтобы модель не писала лишнего текста
        response_format: { type: "json_object" }
      })
    });

    const data = await response.json();

    // 3. Возвращаем ответ фронтенду
    return new Response(JSON.stringify(data), {
      headers: { 'Content-Type': 'application/json' }
    });

  } catch (e) {
    return new Response(
      JSON.stringify({ error: "Ошибка сервера: " + e.message }), 
      { status: 500, headers: { 'Content-Type': 'application/json' } }
    );
  }
}


