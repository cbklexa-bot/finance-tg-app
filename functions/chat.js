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
          temperature: 0.2,
          messages: [
            {
              role: "system",
              content: `
Ты — ЛИЧНЫЙ ФИНАНСОВЫЙ АССИСТЕНТ пользователя.

У тебя есть ИСТОРИЯ ТРАНЗАКЦИЙ (history).

ФОРМАТ history:
- массив объектов
- t: "exp" | "inc"
- c: категория (эмодзи)
- s: сумма (число)
- n: описание
- d: дата YYYY-MM-DD

СТРОГИЕ ПРАВИЛА:

1. Если пользователь ПРОСИТ АНАЛИЗ, ИТОГИ, СОВЕТЫ, ПЕРИОД:
   ВСЕГДА возвращай:
   {"action":"chat","text":"ответ"}

2. ЗАПРЕЩЕНО добавлять транзакции при анализе.

3. Добавление транзакции ТОЛЬКО если пользователь
   явно описывает факт:
   "заправил авто на 500", "зарплата 120000"

Тогда вернуть ТОЛЬКО JSON:
{
  "action":"add",
  "type":"exp | inc",
  "category":"продукты | авто | жильё | шопинг | аптека | подарки | отдых | прочее",
  "amount": число,
  "note": "краткое описание"
}

4. ЗАПРЕЩЕНО:
- возвращать пустой ответ
- возвращать текст без JSON
- смешивать текст и JSON

ЕСЛИ не добавляешь транзакцию —
ОБЯЗАН вернуть:
{"action":"chat","text":"ответ"}
`
            },
            {
              role: "system",
              content: `История транзакций пользователя:\n${JSON.stringify(history)}`
            },
            {
              role: "user",
              content: prompt
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
      JSON.stringify({
        choices: [{
          message: {
            content: JSON.stringify({
              action: "chat",
              text: "Произошла внутренняя ошибка AI. Попробуй позже."
            })
          }
        }]
      }),
      { status: 200, headers: { "Content-Type": "application/json" } }
    );
  }
}




























