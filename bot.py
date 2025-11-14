import logging
import pickle
import os
from datetime import datetime
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    filters, ContextTypes
)
from telegram.error import Forbidden, BadRequest

# ======= НАСТРОЙКИ =======
TOKEN = os.getenv("TOKEN")
FORUM_CHAT_ID = int(os.getenv("FORUM_CHAT_ID"))
STATE_FILE = "bot_state.pkl"

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

user_topics = {}
last_active = {}

# ======= СОХРАНЕНИЕ =======
def save_state():
    with open(STATE_FILE, "wb") as f:
        pickle.dump((user_topics, last_active), f)

def load_state():
    global user_topics, last_active
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "rb") as f:
            user_topics, last_active = pickle.load(f)
        logging.info("🔵 Состояние восстановлено!")

# ======= /start =======
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user

    # Ответ юзеру
    await update.message.reply_text(
        "Приветик, солнышко 🌤\n"
        "Я рядом. Просто напиши мне, и я передам твоё сообщение 💛"
    )

    # Создаем тему
    try:
        topic = await context.bot.create_forum_topic(
            FORUM_CHAT_ID,
            name=f"{user.first_name}"
        )
        user_topics[user.id] = topic.message_thread_id
        save_state()
        logging.info(f"🔵 Создана тема для {user.id}")

    except BadRequest:
        # Тема уже была создана
        logging.info(f"ℹ️ Тема уже существует для {user.id}")

# ======= ПОЛУЧЕНИЕ СООБЩЕНИЙ =======
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    text = update.message.text

    last_active[user.id] = datetime.now()

    # если нет темы → создать
    if user.id not in user_topics:
        try:
            topic = await context.bot.create_forum_topic(
                FORUM_CHAT_ID,
                name=f"{user.first_name}"
            )
            user_topics[user.id] = topic.message_thread_id
            save_state()
        except Exception as e:
            logging.error(f"Ошибка создания темы: {e}")

    thread_id = user_topics.get(user.id)

    # отправка сообщения админу
    try:
        await context.bot.send_message(
            chat_id=FORUM_CHAT_ID,
            message_thread_id=thread_id,
            text=f"✨ Сообщение от {user.first_name}:\n{text}"
        )
        await update.message.reply_text("💌 Сообщение отправлено администраторам!")

    except Forbidden:
        await update.message.reply_text(
            "⚠️ Я не могу ответить тебе.\n"
            "Пожалуйста, нажми /start ещё раз 💛"
        )

    except Exception as e:
        logging.error(f"Ошибка при отправке: {e}")
        await update.message.reply_text("⚠️ Ошибка при отправке.")

# ======= АДМИН ОТВЕЧАЕТ =======
async def reply_to_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.is_topic_message:
        return

    thread_id = update.message.message_thread_id
    text = update.message.text

    user_id = next((u for u, t in user_topics.items() if t == thread_id), None)

    if not user_id:
        await update.message.reply_text("❌ Пользователь не найден.")
        return

    try:
        await context.bot.send_message(
            chat_id=user_id,
            text=f"💬 Ответ администратора:\n{text}"
        )
    except Forbidden:
        await update.message.reply_text("❌ Пользователь заблокировал бота.")

# ======= RUN =======
async def run():
    load_state()

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Chat(FORUM_CHAT_ID) & filters.TEXT, reply_to_user))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logging.info("💖 Бот запущен!")
    await app.run_polling()

if __name__ == "__main__":
    import asyncio
    asyncio.run(run())
