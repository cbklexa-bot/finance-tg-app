export async function onRequestPost(context) {
  const { request, env } = context;

  try {
    const body = await request.json();

    const prompt = body.prompt || "";
    const incomes = body.data?.incomes || [];
    const expenses = body.data?.expenses || [];

    const systemPrompt = `
Ты — личный финансовый ассистент в Telegram Mini App.

ТВОИ ЗАДАЧИ:
1. Если пользователь описывает доход — вернуть JSON income
2. Если пользователь описывает расход — вернуть JSON expense
3. Если пользователь задаёт вопрос или просит анализ — вернуть JSON analysis

ФОРМАТЫ (строго один):

Доход:
{
  "action": "income",
  "amount": number,
  "category": string,
  "note": string
}

Расход:
{
  "action": "expense",
  "amount": number,
  "category": string,
  "note": string
}

Анализ / совет:
{
  "action": "analysis",
  "text": string
}

ДОСТУПНЫЕ ДАННЫЕ:
Доходы: ${JSON.stringify(incomes)}
Расходы: ${JSON.stringify(expenses)}

ПРАВИЛА:
- отвечай ТОЛЬКО валидным JSON
- без markdown
- без пояснений
- без лишнего текста
`;

    const response = await fetch("https://openrouter.ai/api/v1/chat/completions", {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${env.OPENROUTER_API_KEY}`,
        "Content-Type": "application/json",
        "HTTP-Referer": "https://finance-tg-app.pages.dev",
        "X-Title": "Finance TG App"
      },
      body: JSON.stringify({
        model: env.AI_MODEL || "deepseek/deepseek-chat",
        temperature: 0.2,
        messages: [
          { role: "system", content: systemPrompt },
          { role: "user", content: prompt }
        ]
      })
    });

    const data = await response.json();
    const content = data.choices?.[0]?.message?.content;

    return new Response(content, {
      headers: { "Content-Type": "application/json" }
    });

  } catch (e) {
    return new Response(
      JSON.stringify({
        action: "analysis",
        text: "Ошибка обработки запроса. Попробуй ещё раз."
      }),
      { status: 500, headers: { "Content-Type": "application/json" } }
    );
  }
}




