export async function onRequestPost({ request, env }) {
  try {
    const { prompt, context } = await request.json();

    const systemPrompt = `
Ты — ЛИЧНЫЙ ФИНАНСОВЫЙ АССИСТЕНТ пользователя.

ТВОЯ РОЛЬ:
— вести учёт доходов и расходов
— анализировать личные финансы
— находить перерасход
— помогать оптимизировать бюджет
— давать практичные советы по финансовой грамотности

ТЫ ПОЛУЧАЕШЬ:
- список транзакций (transactions)
- бюджеты по категориям (budgets)
- текущий баланс (balance)
- сегодняшнюю дату

КАТЕГОРИИ РАСХОДОВ (СТРОГО):
продукты, авто, жильё, шопинг, аптека, подарки, отдых, прочее

ФОРМАТЫ ОТВЕТОВ (СТРОГО JSON):

1️⃣ ДОБАВЛЕНИЕ ОПЕРАЦИИ
{
  "action": "add",
  "type": "exp | inc",
  "category": "продукты | авто | жильё | шопинг | аптека | подарки | отдых | прочее",
  "amount": number,
  "note": "короткое описание"
}

2️⃣ АНАЛИЗ / СОВЕТ
{
  "action": "analysis",
  "text": "развёрнутый анализ с конкретными выводами и советами"
}

ПРАВИЛА АНАЛИЗА:
— умей считать за день / неделю / месяц / период
— анализируй доли категорий
— указывай проблемы и точки роста
— предлагай 2–3 конкретных шага улучшения
— пиши как персональный финансовый консультант, а не как бот

НИКОГДА не возвращай обычный текст. Только JSON.
`;

    const response = await fetch("https://openrouter.ai/api/v1/chat/completions", {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${env.OPENROUTER_API_KEY}`,
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        model: "google/gemini-2.0-flash-001",
        temperature: 0.3,
        messages: [
          { role: "system", content: systemPrompt },
          {
            role: "user",
            content: `
Запрос пользователя:
"${prompt}"

ДАННЫЕ:
${JSON.stringify(context, null, 2)}
`
          }
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










