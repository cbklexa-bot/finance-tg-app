export async function onRequestPost(context) {
  const { request, env } = context;
  
  try {
    const body = await request.json();

    const response = await fetch("https://openrouter.ai/api/v1/chat/completions", {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${env.OPENROUTER_API_KEY}`,
        "Content-Type": "application/json",
        "HTTP-Referer": "https://pages.dev", 
      },
      body: JSON.stringify({
        model: "deepseek/deepseek-chat",
        messages: [
          { 
            role: "system", 
            content: "Ты — финансовый бот. На любой запрос отвечай ТОЛЬКО JSON-объектом: {\"action\":\"chat\",\"text\":\"твой ответ\"}. Если это трата (сумма и категория), отвечай: {\"action\":\"add\",\"type\":\"exp\",\"amount\":число,\"category\":\"иконка\",\"note\":\"текст\"}." 
          },
          { role: "user", content: body.prompt }
        ],
        response_format: { type: "json_object" }
      })
    });

    const data = await response.json();
    return new Response(JSON.stringify(data), {
      headers: { 'Content-Type': 'application/json' }
    });
  } catch (e) {
    return new Response(JSON.stringify({ error: e.message }), { status: 500 });
  }
}


