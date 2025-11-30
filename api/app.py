import os
import traceback
import sys

from fastapi import FastAPI, Request
from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    PreCheckoutQuery,
    LabeledPrice,
    Update,
)
from aiogram.filters import Command
from redis.asyncio import Redis

# ---------- CONFIG ----------
try:
    BOT_TOKEN = os.environ.get("BOT_TOKEN")
    ADMIN_CHANNEL_STR = os.environ.get("ADMIN_CHANNEL")
    REDIS_URL = os.environ.get("REDIS_URL")

    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN не задан в переменных окружения.")
    if not ADMIN_CHANNEL_STR:
        raise ValueError("ADMIN_CHANNEL не задан в переменных окружения.")
    if not REDIS_URL:
        raise RuntimeError("REDIS_URL не задан в переменных окружения")

    # Преобразуем ADMIN_CHANNEL в число
    try:
        ADMIN_CHANNEL = int(ADMIN_CHANNEL_STR)
    except ValueError:
        raise ValueError(f"ADMIN_CHANNEL должен быть числом, получено: '{ADMIN_CHANNEL_STR}'.")

except Exception as e:
    # Выводим критическую ошибку инициализации, чтобы она появилась в логах Vercel
    print("--------------------------------------------------")
    print(f"КРИТИЧЕСКАЯ ОШИБКА КОНФИГУРАЦИИ: {type(e).__name__}: {e}")
    print("--------------------------------------------------")
    # Завершаем процесс, чтобы Vercel сообщил о сбое
    sys.exit(1)


PRICE_MAIN = 300
PRICE_EXTRA = 50

TITLE_MAIN = "Все локации"
TITLE_EXTRA = "Доп. актив"

DESC_MAIN = "Основной товар за 300⭐"
DESC_EXTRA = "Дополнительный товар за 50⭐"

# ---------- GLOBALS ----------
app = FastAPI()
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
# Redis.from_url автоматически поддерживает rediss://
redis = Redis.from_url(REDIS_URL, decode_responses=True)

MAIN_SET_KEY = "buyers_main"


# ---------- STORAGE ----------
async def user_has_main(user_id: int) -> bool:
    return await redis.sismember(MAIN_SET_KEY, str(user_id))


async def add_main_buyer(user_id: int):
    await redis.sadd(MAIN_SET_KEY, str(user_id))


# ---------- KEYBOARD ----------
def build_keyboard(has_main: bool) -> InlineKeyboardMarkup:
    btns = [[
        InlineKeyboardButton(
            text=f"Купить «{TITLE_MAIN}» за {PRICE_MAIN}⭐",
            callback_data="buy_main",
        )
    ]]
    if has_main:
        btns.append([
            InlineKeyboardButton(
                text=f"Купить «{TITLE_EXTRA}» за {PRICE_EXTRA}⭐",
                callback_data="buy_extra",
            )
        ])
    return InlineKeyboardMarkup(inline_keyboard=btns)


# ---------- HANDLERS ----------
@dp.message(Command("start"))
async def start_handler(msg: Message):
    has_main = await user_has_main(msg.from_user.id)
    await msg.answer(
        "Добро пожаловать! Здесь доступны покупки.",
        reply_markup=build_keyboard(has_main),
    )


@dp.callback_query(F.data == "buy_main")
async def buy_main_handler(callback):
    prices = [LabeledPrice(label=TITLE_MAIN, amount=PRICE_MAIN)]
    await bot.send_invoice(
        chat_id=callback.from_user.id,
        title=TITLE_MAIN,
        description=DESC_MAIN,
        currency="XTR",
        prices=prices,
        payload="main_purchase",
    )
    await callback.answer()


@dp.callback_query(F.data == "buy_extra")
async def buy_extra_handler(callback):
    if not await user_has_main(callback.from_user.id):
        await callback.answer(
            "Доступ к покупкам за 50⭐ только после покупки за 300⭐.",
            show_alert=True,
        )
        return

    prices = [LabeledPrice(label=TITLE_EXTRA, amount=PRICE_EXTRA)]
    await bot.send_invoice(
        chat_id=callback.from_user.id,
        title=TITLE_EXTRA,
        description=DESC_EXTRA,
        currency="XTR",
        prices=prices,
        payload="extra_purchase",
    )
    await callback.answer()


@dp.pre_checkout_query()
async def checkout_handler(pre: PreCheckoutQuery):
    await bot.answer_pre_checkout_query(pre.id, ok=True)


@dp.message(F.successful_payment)
async def payment_success(msg: Message):
    payload = msg.successful_payment.invoice_payload
    user = msg.from_user

    if payload == "main_purchase":
        await add_main_buyer(user.id)
        title = TITLE_MAIN
        price = PRICE_MAIN
    elif payload == "extra_purchase":
        title = TITLE_EXTRA
        price = PRICE_EXTRA
    else:
        return

    await msg.answer(f"Товар «{title}» активирован!")

    text_admin = (
        "📩 Новый заказ!\n"
        f"Покупатель: @{user.username or 'нет username'}\n"
        f"ID: {user.id}\n"
        f"Товар: {title}\n"
        f"Оплата: {price}⭐"
    )

    # если сообщение в канал упадёт (бот не админ и т.п.) — не роняем весь вебхук
    try:
        await bot.send_message(ADMIN_CHANNEL, text_admin)
    except Exception:
        print(f"Ошибка при отправке в ADMIN_CHANNEL={ADMIN_CHANNEL}")
        traceback.print_exc()

    has_main = await user_has_main(user.id)
    await msg.answer("Меню обновлено:", reply_markup=build_keyboard(has_main))


# ---------- HEALTHCHECK ----------
@app.get("/")
async def healthcheck():
    return {"status": "ok"}


# ---------- WEBHOOK ----------
@app.post("/")
async def telegram_webhook(request: Request):
    data = await request.json()
    print("Incoming update:", data)

    try:
        if hasattr(Update, "model_validate"):
            update = Update.model_validate(data)
        else:
            update = Update(**data)
    except Exception:
        print("Ошибка парсинга Update")
        traceback.print_exc()
        return {"ok": True}

    try:
        await dp.feed_update(bot, update)
    except Exception:
        print("Ошибка в обработчике апдейта")
        traceback.print_exc()
        # не отдаём 500 Telegram’у
    return {"ok": True}
