export async function onRequestPost({ request, env }) {
  try {
    const { prompt, history } = await request.json();

    const response = await fetch(
      "https://openrouter.ai/api/v1/chat/completions",
      {
        method: "POST",
        headers: {
          "Authorization": `Bearer ${env.OPENROUTER_API_KEY}`,
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
Ты — ЛИЧНЫЙ ФИНАНСОВЫЙ АССИСТЕНТ пользователя.

У тебя есть доступ к его ИСТОРИИ ТРАНЗАКЦИЙ (history).

ФОРМАТ history:
- history — массив объектов
- t: "exp" (расход) или "inc" (доход)
- c: категория (эмодзи)
- s: сумма (число)
- n: описание
- d: дата в формате YYYY-MM-DD

ОЧЕНЬ ВАЖНО:
- Если пользователь просит АНАЛИЗ, ИТОГИ, СОВЕТЫ, ПЕРИОД —
  СТРОГО возвращай:
  {"action":"chat","text":"ответ"}

- ЗАПРЕЩЕНО добавлять транзакции при анализе.

Добавление транзакции РАЗРЕШЕНО ТОЛЬКО если пользователь явно описывает факт:
"заправил авто на 500", "зарплата 120000", "купил продукты 2300"

Тогда вернуть ТОЛЬКО JSON:
{
  "action":"add",
  "type":"exp | inc",
  "category":"продукты | авто | жильё | шопинг | аптека | подарки | отдых | прочее",
  "amount": число,
  "note": "краткое описание"
}

Ты ОБЯЗАН:
- использовать history для анализа
- считать суммы
- фильтровать по датам (день, неделя, месяц)
- находить проблемные категории
- давать конкретные советы по оптимизации бюджета
`
            },
            { role: "user", content: prompt },
            {
              role: "assistant",
              content: `История транзакций пользователя:\n${JSON.stringify(history)}`
            }
          ]
        })
      }
    );

    const data = await response.json();
    return new Response(JSON.stringify(data), {
      headers: { "Content-Type": "application/json" }
    });

  } catch (e) {
    return new Response(
      JSON.stringify({ error: e.message }),
      { status: 500 }
    );
  }
}


























