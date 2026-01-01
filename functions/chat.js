export async function onRequestPost({ request, env }) {
  try {
    const { prompt, history } = await request.json();
    const today = new Date().toLocaleDateString('ru-RU');

    const response = await fetch("https://openrouter.ai/api/v1/chat/completions", {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${env.OPENROUTER_API_KEY}`,
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        model: "google/gemini-2.0-flash-001",
        messages: [
          {
            role: "system",
            content: `Ты — продвинутый финансовый аналитик. Твоя задача — классифицировать траты по СТРОГИМ категориям пользователя.

            СПИСОК ТВОИХ КАТЕГОРИЙ:
            1. продукты (еда, хлеб, напитки, супермаркеты)
            2. авто (заправка, бензин, запчасти, ремонт колеса, мойка, сервис)
            3. жильё (интернет, электричество, свет, вода, аренда, ЖКХ, газ)
            4. шопинг (одежда, техника, электроника)
            5. аптека (лекарства, аптеки, врачи)
            6. подарки (цветы, донаты, подарки друзьям)
            7. отдых (кино, кафе, рестораны, бары, хобби)
            8. прочее (все остальное)

            ИНСТРУКЦИЯ:
            - Если пользователь пишет про машину (колесо, бензин, запчасти) -> категория "авто".
            - Если пишет про дом (свет, ток, интернет, коммуналка) -> категория "жильё".
            - Верни ТОЛЬКО JSON: {"action":"add", "type":"exp", "category":"название_категории_из_списка", "amount":число, "note":"подробное описание"}
            - Если это вопрос или анализ -> {"action":"chat", "text":"твой ответ"}.`
          },
          { role: "user", content: prompt }
        ]
      })
    });

    const data = await response.json();
    return new Response(JSON.stringify(data), { headers: { "Content-Type": "application/json" } });
  } catch (e) {
    return new Response(JSON.stringify({ error: e.message }), { status: 500 });
  }
}








