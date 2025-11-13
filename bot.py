import logging  
import pickle
import os
from datetime import datetime
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    filters, ContextTypes
)
from telegram.error import Forbidden

TOKEN = os.getenv("TOKEN")
FORUM_CHAT_ID = int(os.getenv("FORUM_CHAT_ID"))
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
        logging.info("🔵 Состояние восстановлено!")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Приветик, солнышко 🌤\n"
        "Я рядом. Просто напиши мне 💛"
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    text = update.message.text

    last_active[user.id] = datetime.now()

    try:
        if user.id in user_topics:
            thread_id = user_topics[user.id]
        else:
            topic = await context.bot.create_forum_topic(
                FORUM_CHAT_ID,
                name=f"{user.first_name}"
            )
            thread_id = topic.message_thread_id
            user_topics[user.id] = thread_id
            save_state()

        await context.bot.send_message(
            chat_id=FORUM_CHAT_ID,
            message_thread_id=thread_id,
            text=f"✨ Сообщение от {user.first_name}:\n{text}"
        )

        await update.message.reply_text("💌 Сообщение отправлено администраторам!")

    except Exception as e:
        logging.error(f"Ошибка: {e}")
        await update.message.reply_text("⚠️ Ошибка при отправке.")


async def reply_to_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.is_topic_message:
        return

    thread_id = update.message.message_thread_id
    text = update.message.text

    user_id = next((uid for uid, tid in user_topics.items() if tid == thread_id), None)

    if user_id:
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=f"💬 Ответ администратора:\n{text}"
            )
        except Forbidden:
            await update.message.reply_text("❌ Пользователь заблокировал бота.")
    else:
        await update.message.reply_text("❌ Пользователь не найден.")


async def who(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.is_topic_message:
        await update.message.reply_text("❗ Используй команду внутри темы.")
        return

    thread_id = update.message.message_thread_id
    user_id = next((uid for uid, tid in user_topics.items() if tid == thread_id), None)

    if user_id:
        await update.message.reply_text(
            f"🆔 ID пользователя: `{user_id}`",
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text("❌ Пользователь не найден.")


# =============== ЗАПУСК ДЛЯ RENDER ==================
def main():
    load_state()

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("who", who))
    app.add_handler(MessageHandler(filters.Chat(FORUM_CHAT_ID) & filters.TEXT, reply_to_user))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logging.info("💖 Бот запущен!")
    app.run_polling()


if __name__ == "__main__":
    main()
