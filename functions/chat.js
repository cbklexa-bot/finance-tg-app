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
Ты — личный финансовый ассистент пользователя.

ТЫ УМЕЕШЬ:
— записывать доходы и расходы
— анализировать историю транзакций
— считать суммы за любой период
— находить перерасход
— давать финансовые рекомендации

КРИТИЧЕСКОЕ ПРАВИЛО:
❌ НЕ записывай транзакцию, если:
— это приветствие
— вопрос
— анализ
— просьба о совете
— нет суммы

ТРАНЗАКЦИЯ — ТОЛЬКО если есть сумма и действие.

Если передана история, она выглядит так:
Дата | Тип | Категория | Сумма | Описание

История:
${history || "Нет данных"}

Формат ответа:
— для записи: {"action":"add","type":"exp|inc","category":"...","amount":число,"note":"..."}
— для общения/анализа: {"action":"chat","text":"ответ"}
`
          },
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






















