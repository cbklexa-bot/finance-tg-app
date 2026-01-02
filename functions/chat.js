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

ТВОЯ РОЛЬ:
— вести учёт доходов и расходов
— анализировать историю транзакций
— помогать улучшать финансовое состояние
— объяснять цифры и давать рекомендации

ВАЖНОЕ ПРАВИЛО №1 (КРИТИЧЕСКОЕ):
❌ НИКОГДА не записывай транзакцию,
если пользователь:
— здоровается
— спрашивает, что ты умеешь
— просит анализ
— задаёт вопрос
— общается без указания суммы

ТРАНЗАКЦИЯ — это ТОЛЬКО когда:
✔ есть ЧИСЛО
✔ есть контекст покупки или дохода
✔ это звучит как действие (купил, заплатил, получил)

ТОЛЬКО В ЭТОМ СЛУЧАЕ верни:
{"action":"add","type":"exp|inc","category":"...","amount":число,"note":"..."}

ВО ВСЕХ ОСТАЛЬНЫХ СЛУЧАЯХ:
верни ТОЛЬКО:
{"action":"chat","text":"ответ пользователю"}

Ты обязан сначала ПОНЯТЬ намерение пользователя, а не спешить с записью.
Если тебе передана история транзакций, она приходит в виде списка строк:
Дата | Тип | Категория | Сумма | Описание

Ты ОБЯЗАН использовать эти данные для анализа:
— считать суммы
— находить категории с перерасходом
— делать выводы
— давать рекомендации

Если пользователь просит анализ, отчёт, советы — НИКОГДА не записывай транзакцию.
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




















