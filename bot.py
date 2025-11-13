import logging
import pickle
import os
from datetime import datetime, timedelta

from aiohttp import web
from telegram import Update
from telegram.error import Forbidden
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

# -------------------------
# НАСТРОЙКИ
# -------------------------
TOKEN = os.getenv("TOKEN")
FORUM_CHAT_ID = int(os.getenv("FORUM_CHAT_ID"))
STATE_FILE = "bot_state.pkl"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

# Храним темы и активность
user_topics = {}
last_active = {}

# -------------------------
# Восстановление состояния
# -------------------------
def save_state():
    with open(STATE_FILE, "wb") as f:
        pickle.dump((user_topics, last_active), f)

def load_state():
    global user_topics, last_active
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "rb") as f:
            user_topics, last_active = pickle.load(f)
        logging.info("Состояние восстановлено!")

# -------------------------
# Команда /start
# -------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Приветик, солнышко 🌤\n"
        "Я рядом. Просто напиши мне любое сообщение 💛"
    )

# -------------------------
# Пользователь → админ
# -------------------------
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
            text=f"💬 Сообщение от *{user.first_name}*:\n{text}",
            parse_mode='Markdown'
        )

        await update.message.reply_text("💛 Сообщение отправлено администраторам!")

    except Exception as e:
        logging.error(f"Ошибка отправки: {e}")
        await update.message.reply_text("⚠ Произошла ошибка при отправке сообщения.")

# -------------------------
# Админ → пользователь (команда /ban)
# -------------------------
async def reply_to_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.is_topic_message:
        return

    thread_id = update.message.message_thread_id
    text = update.message.text

    user_id = next((u for u, t in user_topics.items() if t == thread_id), None)
    if not user_id:
        await update.message.reply_text("❌ Пользователь не найден.")
        return

    # команда /ban
    if text.startswith("/ban"):
        try:
            await context.bot.ban_chat_member(FORUM_CHAT_ID, user_id)
            await update.message.reply_text("🚫 Пользователь заблокирован.")
        except Exception as e:
            await update.message.reply_text(f"Ошибка бана: {e}")
        return

    # обычный ответ
    try:
        await context.bot.send_message(
            chat_id=user_id,
            text=f"✉ Ответ администратора:\n{text}",
            parse_mode="Markdown"
        )
    except Forbidden:
        await update.message.reply_text("❌ Пользователь заблокировал бота.")

# -------------------------
# Вебхук-хендлер для Render
# -------------------------
async def webhook_handler(request):
    data = await request.json()
    await application.update_queue.put(Update.de_json(data, application.bot))
    return web.Response(text="OK")

# -------------------------
# Запуск
# -------------------------
async def main():
    load_state()

    global application
    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.Chat(FORUM_CHAT_ID) & filters.TEXT, reply_to_user))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    app = web.Application()
    app.router.add_post("/", webhook_handler)

    # стартуем веб-сервер
    await application.initialize()
    await application.start()
    runner = web.AppRunner(app)
    await runner.setup()

    site = web.TCPSite(runner, "0.0.0.0", int(os.getenv("PORT", 10000)))
    await site.start()

    logging.info("Бот запущен и слушает вебхук...")

    await application.updater.start_polling()
    await application.updater.idle()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
