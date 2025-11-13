import logging
import pickle
import os
from datetime import datetime
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ContextTypes, filters
)
from telegram.error import Forbidden

TOKEN = os.getenv("TOKEN")
FORUM_CHAT_ID = int(os.getenv("FORUM_CHAT_ID"))
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET")
BASE_URL = os.getenv("RENDER_EXTERNAL_URL")

STATE_FILE = "bot_state.pkl"

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

user_topics = {}
last_active = {}


def save_state():
    with open(STATE_FILE, "wb") as f:
        pickle.dump((user_topics, last_active), f)


def load_state():
    global user_topics, last_active
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "rb") as f:
            user_topics, last_active = pickle.load(f)
        logging.info("State loaded.")


# ---------------- START ----------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет 😊\nПиши свою проблему, я передам её администраторам!"
    )


# ---------------- USER → FORUM ----------------
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    text = update.message.text

    last_active[user.id] = datetime.utcnow()

    # Тема уже существует?
    if user.id in user_topics:
        thread_id = user_topics[user.id]
    else:
        # создаем новую тему
        topic = await context.bot.create_forum_topic(
            chat_id=FORUM_CHAT_ID,
            name=f"{user.first_name} ({user.id})"
        )
        thread_id = topic.message_thread_id
        user_topics[user.id] = thread_id
        save_state()

    # отправляем сообщение в тему форума
    await context.bot.send_message(
        chat_id=FORUM_CHAT_ID,
        message_thread_id=thread_id,
        text=f"💬 Сообщение от **{user.first_name}** (ID: `{user.id}`):\n{text}",
        parse_mode="Markdown"
    )

    await update.message.reply_text("✉️ Сообщение отправлено модераторам!")


# ---------------- ADMIN → USER ----------------
async def reply_to_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.is_topic_message:
        return

    admin_text = update.message.text
    thread_id = update.message.message_thread_id

    user_id = next((u for u, t in user_topics.items() if t == thread_id), None)
    if not user_id:
        return await update.message.reply_text("Пользователь не найден.")

    try:
        await context.bot.send_message(
            chat_id=user_id,
            text=f"💛 Ответ администратора:\n{admin_text}"
        )
    except Forbidden:
        await update.message.reply_text("⚠ Пользователь заблокировал бота.")

    last_active[user_id] = datetime.utcnow()
    save_state()


# ---------------- RUN WEBHOOK (обязательно для Render) ----------------
async def run():
    load_state()

    app = ApplicationBuilder()\
        .token(TOKEN)\
        .webhook_url(f"{BASE_URL}/{WEBHOOK_SECRET}")\
        .build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Chat(FORUM_CHAT_ID) & filters.TEXT, reply_to_user))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logging.info("Bot started via WEBHOOK.")

    await app.run_webhook(
        listen="0.0.0.0",
        port=10000,
        url_path=WEBHOOK_SECRET,
    )


if __name__ == "__main__":
    import asyncio
    asyncio.run(run())
