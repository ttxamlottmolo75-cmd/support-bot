import logging
import os
import pickle
from datetime import datetime, timedelta

from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ContextTypes, filters
)
from telegram.error import Forbidden


TOKEN = os.getenv("TOKEN")
FORUM_CHAT_ID = int(os.getenv("FORUM_CHAT_ID"))
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET")
BASE_URL = os.getenv("RENDER_EXTERNAL_URL")  # автоматическая переменная Render

STATE_FILE = "bot_state.pkl"


# -------------------- LOGGING --------------------
logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)


# ------------ ХРАНИЛИЩЕ СОСТОЯНИЙ ------------
user_topics = {}
last_active = {}  # для авто-закрытия тем


def save_state():
    with open(STATE_FILE, "wb") as f:
        pickle.dump((user_topics, last_active), f)


def load_state():
    global user_topics, last_active
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "rb") as f:
            user_topics, last_active = pickle.load(f)
        logging.info("Состояние восстановлено.")


# -------------------- START --------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет 🧡\nМожешь написать мне любую проблему — я передам её модераторам."
    )


# -------------------- ПОЛЬЗОВАТЕЛЬ → АДМИНЫ --------------------
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    text = update.message.text

    last_active[user.id] = datetime.utcnow()

    # если у пользователя уже создана тема
    if user.id in user_topics:
        thread = user_topics[user.id]
    else:
        # создаём новую тему
        topic = await context.bot.create_forum_topic(
            chat_id=FORUM_CHAT_ID,
            name=f"{user.first_name} ({user.id})"
        )
        thread = topic.message_thread_id
        user_topics[user.id] = thread
        save_state()

    # отправляем сообщение в тему
    await context.bot.send_message(
        chat_id=FORUM_CHAT_ID,
        message_thread_id=thread,
        text=f"📩 Сообщение от **{user.first_name}** (ID: `{user.id}`):\n\n{text}",
        parse_mode="Markdown"
    )

    await update.message.reply_text("Готово! Я передал твоё сообщение 💛")


# -------------------- АДМИН ОТВЕТЫ → ПОЛЬЗОВАТЕЛЮ --------------------
async def reply_to_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.is_topic_message:
        return

    thread_id = update.message.message_thread_id
    admin_text = update.message.text

    # ищем пользователя по ID темы
    user_id = None
    for uid, tid in user_topics.items():
        if tid == thread_id:
            user_id = uid
            break

    if not user_id:
        await update.message.reply_text("⚠️ Не могу найти пользователя.")
        return

    try:
        await context.bot.send_message(
            chat_id=user_id,
            text=f"💬 Ответ администратора:\n{admin_text}"
        )
    except Forbidden:
        await update.message.reply_text("❌ Пользователь заблокировал бота.")

    last_active[user_id] = datetime.utcnow()
    save_state()


# -------------------- /who ДЛЯ АДМИНОВ --------------------
async def who(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.is_topic_message:
        return await update.message.reply_text("Используй в теме форума.")

    thread_id = update.message.message_thread_id

    user_id = next((u for u, t in user_topics.items() if t == thread_id), None)
    if user_id:
        await update.message.reply_text(f"🆔 ID пользователя: `{user_id}`", parse_mode="Markdown")
    else:
        await update.message.reply_text("Пользователь не найден.")


# -------------------- WEBHOOK START --------------------
async def run():
    load_state()

    app = (
        ApplicationBuilder()
        .token(TOKEN)
        .webhook_url(f"{BASE_URL}/{WEBHOOK_SECRET}")
        .build()
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("who", who))
    app.add_handler(MessageHandler(filters.Chat(FORUM_CHAT_ID) & filters.TEXT, reply_to_user))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logging.info("Бот запущен на webhook!")
    await app.run_webhook(
        listen="0.0.0.0",
        port=10000,
        url_path=WEBHOOK_SECRET,
    )


if __name__ == "__main__":
    import asyncio
    asyncio.run(run())
