import logging
import os
import pickle
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
BASE_URL = os.getenv("RENDER_EXTERNAL_URL")   # Render сам создаёт

STATE_FILE = "bot_state.pkl"

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

# ---------------- ХРАНЕНИЕ СОСТОЯНИЙ ----------------
user_topics = {}   # user_id → thread_id
last_active = {}   


def save_state():
    with open(STATE_FILE, "wb") as f:
        pickle.dump((user_topics, last_active), f)


def load_state():
    global user_topics, last_active
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "rb") as f:
            user_topics, last_active = pickle.load(f)
        logging.info("Состояние загружено")


# ---------------- START ----------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет 🧡\nНапиши свою проблему, и я передам её модераторам!"
    )


# ---------------- Пользователь → Админы ----------------
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    text = update.message.text

    last_active[user.id] = datetime.utcnow()

    # если у юзера уже есть тема
    if user.id in user_topics:
        thread_id = user_topics[user.id]
    else:
        topic = await context.bot.create_forum_topic(
            chat_id=FORUM_CHAT_ID,
            name=f"{user.first_name} ({user.id})"
        )
        thread_id = topic.message_thread_id
        user_topics[user.id] = thread_id
        save_state()

    await context.bot.send_message(
        chat_id=FORUM_CHAT_ID,
        message_thread_id=thread_id,
        text=f"📩 Сообщение от **{user.first_name}** (ID: `{user.id}`):\n\n{text}",
        parse_mode="Markdown"
    )

    await update.message.reply_text("Готово, я передал твой текст 💛")


# ---------------- Админ → Пользователь ----------------
async def reply_to_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.is_topic_message:
        return

    admin_text = update.message.text
    thread_id = update.message.message_thread_id

    user_id = next((u for u, t in user_topics.items() if t == thread_id), None)

    if not user_id:
        return await update.message.reply_text("⚠️ Пользователь не найден")

    try:
        await context.bot.send_message(
            chat_id=user_id,
            text=f"💬 Ответ администратора:\n{admin_text}"
        )
    except Forbidden:
        await update.message.reply_text("❌ Пользователь заблокировал бота")

    last_active[user_id] = datetime.utcnow()
    save_state()


# ---------------- BAN ----------------
async def ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.is_topic_message:
        return await update.message.reply_text("❗ Используй внутри темы.")

    if not context.args:
        return await update.message.reply_text("Напиши: /ban  Пример: /ban спам")

    reason = " ".join(context.args)

    thread_id = update.message.message_thread_id
    user_id = next((u for u, t in user_topics.items() if t == thread_id), None)

    if not user_id:
        return await update.message.reply_text("❌ Юзер не найден.")

    user_topics.pop(user_id, None)
    save_state()

    await update.message.reply_text(f"🚫 Пользователь заблокирован.\nПричина: {reason}")


# ---------------- WHO ----------------
async def who(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.is_topic_message:
        return await update.message.reply_text("❗ Используй только в теме форума")

    thread_id = update.message.message_thread_id
    user_id = next((u for u, t in user_topics.items() if t == thread_id), None)

    if user_id:
        await update.message.reply_text(f"🆔 ID: `{user_id}`", parse_mode="Markdown")
    else:
        await update.message.reply_text("Пользователь не найден")


# ---------------- СТАРТ ЧЕРЕЗ WEBHOOK ----------------
async def run():
    load_state()

    app = ApplicationBuilder()\
        .token(TOKEN)\
        .webhook_url(f"{BASE_URL}/{WEBHOOK_SECRET}")\
        .build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("who", who))
    app.add_handler(CommandHandler("ban", ban))

    app.add_handler(MessageHandler(filters.Chat(FORUM_CHAT_ID) & filters.TEXT, reply_to_user))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logging.info("Бот запущен через webhook!")

    await app.run_webhook(
        listen="0.0.0.0",
        port=10000,
        url_path=WEBHOOK_SECRET,
    )


if __name__ == "__main__":
    import asyncio
    asyncio.run(run())
