export async function onRequestPost({ request, env }) {
  try {
    const { prompt, history } = await request.json();

    const response = await fetch("https://openrouter.ai/api/v1/chat/completions", {
      method: "POST",
      headers: {
        "Authorization": "Bearer " + env.OPENROUTER_API_KEY,
        "Content-Type": "application/json",
        "HTTP-Referer": "https://finance-tg-app.pages.dev",
        "X-Title": "Finance TG App"
      },
      body: JSON.stringify({
        model: "google/gemini-2.0-flash-001",
        messages: [
          {
            role: "system",
            content: `
Ты — умный личный финансовый помощник пользователя.

ТЫ УМЕЕШЬ:
• автоматически записывать доходы и расходы
• анализировать историю транзакций
• считать итоги за любой период
• находить перерасход
• давать советы по оптимизации бюджета

КАТЕГОРИИ (СТРОГО):
продукты, авто, жильё, шопинг, аптека, подарки, отдых, прочее

ЕСЛИ пользователь вводит транзакцию:
Верни ТОЛЬКО JSON:
{"action":"add","type":"exp|inc","category":"категория","amount":число,"note":"описание"}

ЕСЛИ пользователь спрашивает анализ:
Верни:
{"action":"chat","text":"подробный анализ с цифрами и советами"}

У тебя есть история операций пользователя, используй её для анализа.
`
          },
          ...(history || []).map(h => ({
            role: "user",
            content: `${h.d} ${h.t === "exp" ? "расход" : "доход"} ${h.s}₽ ${h.n}`
          })),
          { role: "user", content: prompt }
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












