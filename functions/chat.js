export async function onRequestPost(context) {
  const { request, env } = context;

  try {
    const { prompt } = await request.json();

    // Замени на свой ключ или добавь его в панель Cloudflare -> Pages -> Settings -> Variables
    const OPENROUTER_API_KEY = env.OPENROUTER_API_KEY; 

    const response = await fetch("https://openrouter.ai/api/v1/chat/completions", {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${OPENROUTER_API_KEY}`,
        "Content-Type": "application/json",
        "HTTP-Referer": "https://finance-tg-app.pages.dev", // Твой домен
        "X-Title": "Finance TG App"
      },
      body: JSON.stringify({
        "model": "google/gemini-2.0-flash-001", // Можно поменять на любую модель
        "messages": [
          {
            "role": "system",
            "content": "Ты финансовый помощник. Если пользователь пишет транзакцию (например 'Такси 500'), верни ТОЛЬКО JSON: {\"action\":\"add\", \"type\":\"exp\", \"category\":\"🚗\", \"amount\":500, \"note\":\"Такси\"}. Если это вопрос, верни JSON: {\"action\":\"chat\", \"text\":\"твой ответ\"}. Категории только: 🛒, 🚗, 🏠, 🛍️, 💊, 🎁, 🎭, 📦, 💵, 📈"
          },
          { "role": "user", "content": prompt }
        ]
      })
    });

    const data = await response.json();
    return new Response(JSON.stringify(data), {
      headers: { "Content-Type": "application/json" }
    });

  } catch (e) {
    return new Response(JSON.stringify({ error: e.message }), { status: 500 });
  }
}


