import logging
import pickle
import os
import time
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
)
from telegram.error import Forbidden, BadRequest

# ============ НАСТРОЙКИ ============
import os
TOKEN = os.getenv("TOKEN")
FORUM_CHAT_ID = int(os.getenv("FORUM_CHAT_ID"))
STATE_FILE = "bot_state.pkl"
CLEAR_AFTER_DAYS = 7
# ==================================

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
        logging.info("🔄 Состояние восстановлено!")

# ======== АВТОЧИСТКА СТАРЫХ ТЕМ ========
async def clear_inactive_topics(context: ContextTypes.DEFAULT_TYPE):
    now = datetime.now()
    to_delete = []

    for user_id, last_time in list(last_active.items()):
        if now - last_time > timedelta(days=CLEAR_AFTER_DAYS):
            to_delete.append(user_id)

    for uid in to_delete:
        try:
            thread_id = user_topics[uid]
            await context.bot.close_forum_topic(FORUM_CHAT_ID, thread_id)
            del user_topics[uid]
            del last_active[uid]
            logging.info(f"🧹 Тема пользователя {uid} очищена (не активен).")
        except Exception as e:
            logging.warning(f"Не удалось удалить тему {uid}: {e}")

    if to_delete:
        save_state()

# ======== КОМАНДЫ ========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Приветик, солнце! 🌤 Этот бот — для общения и поддержки.\n"
        "Просто напиши сообщение — и мы ответим тебе 💌\n\n"
        "📜 *Правила:*\n"
        "• Без спама и оскорблений.\n"
        "• Не кидаем ссылки на другие соцсети.\n"
        "• Уважай собеседников. 💖",
        parse_mode="Markdown"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    text = update.message.text
    last_active[user.id] = datetime.now()

    try:
        if user.id in user_topics:
            thread_id = user_topics[user.id]
        else:
            topic = await context.bot.create_forum_topic(FORUM_CHAT_ID, name=f"{user.first_name}")
            thread_id = topic.message_thread_id
            user_topics[user.id] = thread_id
            save_state()

        await context.bot.send_message(
            chat_id=FORUM_CHAT_ID,
            message_thread_id=thread_id,
            text=f"✨ Новое сообщение от {user.first_name}:\n{text}\n\n📜 Напоминание:\n• Без оскорблений\n• Не кидаем ссылки\n• Уважай всех 💖",
            parse_mode="Markdown"
        )
        await update.message.reply_text("💌 Сообщение отправлено администраторам!")

    except Exception as e:
        logging.error(f"Ошибка при отправке: {e}")
        await update.message.reply_text("⚠️ Не удалось переслать сообщение.")

async def reply_to_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.is_topic_message:
        return

    thread_id = update.message.message_thread_id
    text = update.message.text
    user_id = next((uid for uid, tid in user_topics.items() if tid == thread_id), None)

    if user_id:
        try:
            await context.bot.send_message(chat_id=user_id, text=f"💬 Ответ от администратора:\n{text}")
        except Forbidden:
            await update.message.reply_text("❌ Пользователь заблокировал бота.")

async def who(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.is_topic_message:
        await update.message.reply_text("❗ Используй команду внутри темы.")
        return

    thread_id = update.message.message_thread_id
    user_id = next((uid for uid, tid in user_topics.items() if tid == thread_id), None)
    if user_id:
        await update.message.reply_text(f"🆔 ID пользователя: `{user_id}`", parse_mode="Markdown")
    else:
        await update.message.reply_text("❌ Пользователь не найден.")

async def ban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Использование: /ban user_id")
        return

    user_id = int(context.args[0])
    try:
        await context.bot.ban_chat_member(FORUM_CHAT_ID, user_id)
        await update.message.reply_text(f"🚫 Пользователь {user_id} заблокирован!")
    except Exception as e:
        await update.message.reply_text(f"⚠️ Ошибка: {e}")

# ======== ЗАПУСК ========
def main():
    load_state()

    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("who", who))
    app.add_handler(CommandHandler("ban", ban_user))
    app.add_handler(MessageHandler(filters.Chat(FORUM_CHAT_ID) & filters.TEXT, reply_to_user))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    app.job_queue.run_repeating(clear_inactive_topics, interval=86400, first=60)

    logging.info("🚀 Бот запущен и слушает сообщения.")
    app.run_polling(close_loop=False)

if __name__ == "__main__":
    while True:
        try:
            main()
        except Exception as e:
            logging.error(f"💥 Ошибка: {e}")
            logging.info("♻️ Перезапуск через 5 секунд...")
            time.sleep(5)
