# Telegram Bot (aiogram 3 + FastAPI + Vercel)

Минимальный пример бота с оплатой в Telegram Stars, адаптированный под деплой на Vercel.

## Структура

- `api/bot.py` — FastAPI-приложение + aiogram Dispatcher, работа через webhook.
- `requirements.txt` — зависимости для Vercel.
- `buyers.json` — локальное хранилище покупок **только для разработки**, на Vercel данные не сохраняются.

## Быстрый старт локально

```bash
python -m venv venv
source venv/bin/activate  # или venv\Scripts\activate на Windows
pip install -r requirements.txt

export BOT_TOKEN="YOUR_BOT_TOKEN"
# затем подставь его в код или сделай чтение из env

uvicorn api.bot:app --reload
```

Потом в Telegram:

```bash
curl "https://api.telegram.org/botYOUR_BOT_TOKEN/setWebhook?url=https://your-ngrok-url.ngrok-free.app/"
```

## Деплой на Vercel

1. Залей репозиторий на GitHub.
2. Подключи его в Vercel.
3. Укажи `BOT_TOKEN` и `ADMIN_CHANNEL` как Environment Variables.
4. Деплой.
5. Вызови `setWebhook` на `https://<project>.vercel.app/api/bot`.
