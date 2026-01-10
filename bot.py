@app.route('/chat', methods=['POST'])
def chat_ai():
    try:
        data = request.json
        prompt = data.get('prompt') or ""
        user_id = data.get('user_id')

        # 1. СБОР ИСТОРИИ (Читаем из колонки data)
        history_text = "История операций пуста."
        if user_id:
            try:
                # Берем последние 50 записей
                res = supabase.table("finance").select("data").eq("user_id", str(user_id)).order("created_at", desc=True).limit(50).execute()
                if res.data:
                    lines = []
                    for item in res.data:
                        d = item.get('data', {})
                        if isinstance(d, str): d = json.loads(d) # на случай если в базе строка
                        
                        t_type = "Расход" if d.get('t') == 'exp' else "Доход"
                        # Передаем ИИ в максимально понятном виде
                        lines.append(f"- {d.get('d')}: {t_type} {d.get('c')} {d.get('s')}р. ({d.get('n')})")
                    history_text = "\n".join(lines)
            except Exception as e:
                print(f"DB Read Error: {e}")

        # 2. ИНСТРУКЦИЯ (Учим ИИ работать с вашей структурой)
        system_instruction = f"""
        Ты финансовый ассистент. Сегодня: {datetime.now().strftime("%Y-%m-%d")}.
        Твой формат записи: [JSON_DATA]{{"s": сумма, "c": "иконка", "t": "exp|inc", "n": "название"}}[/JSON_DATA]

        ИСТОРИЯ ОПЕРАЦИЙ:
        {history_text}

        ПРАВИЛА:
        1. Если просят записать — ответь коротко и дай JSON.
        2. Если просят анализ (например, "сколько потратил на молоко") — считай только по истории выше.
        3. Используй категории: 🛒 Продукты, 🚗 Авто, 🏠 Жильё, 🛍️ Шопинг, 💊 Аптека, 🎭 Отдых, 🎁 Подарки, 💵 Зарплата, 📈 Инвест, 📦 Прочее.
        """

        # 3. ЗАПРОС К OPENROUTER
        headers = {"Authorization": f"Bearer {OR_KEY}", "Content-Type": "application/json"}
        payload = {
            "model": "deepseek/deepseek-chat",
            "messages": [
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.2
        }
        
        response_raw = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload, timeout=60)
        ai_message = response_raw.json()['choices'][0]['message']['content']

        # 4. СОХРАНЕНИЕ В БАЗУ (Если ИИ решил что-то записать)
        if "[JSON_DATA]" in ai_message:
            match = re.search(r"\[JSON_DATA\]([\s\S]*?)\[/JSON_DATA\]", ai_message)
            if match and user_id:
                try:
                    tx = json.loads(match.group(1).strip())
                    tx['d'] = datetime.now().strftime("%Y-%m-%d") # Ставим дату
                    tx['id'] = int(time.time() * 1000)            # Генерируем ID

                    # Пишем в колонку data
                    supabase.table("finance").insert({
                        "user_id": str(user_id),
                        "data": tx
                    }).execute()
                    
                    # Убираем JSON из ответа пользователю (фронтенд его и так увидит)
                    ai_message = re.sub(r"\[JSON_DATA\].*?\[\/JSON_DATA\]", "", ai_message, flags=re.DOTALL).strip()
                except Exception as e:
                    print(f"Insert error: {e}")

        return jsonify({"choices": [{"message": {"content": ai_message}}]})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
