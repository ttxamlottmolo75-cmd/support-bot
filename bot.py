import os
import pickle
import logging
from datetime import datetime, timedelta

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from telegram import Bot, Update
from telegram.ext import Application, ContextTypes

logging.basicConfig(level=logging.INFO)

TOKEN = os.getenv("TOKEN")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET")  # Защита вебхука
FORUM_CHAT_ID = int(os.getenv("FORUM_CHAT_ID"))

bot = Bot(token=TOKEN)

STATE_FILE = "bot_state.pkl"
user_topics = {}
last_active = {}

# -------------------- LOAD/SAVE STATE ----------------------

def save_state():
    with open(STATE_FILE, "wb") as f:
        pickle.dump((user_topics, last_active), f)
    logging.info("State saved.")

def load_state():
    global user_topics, last_active
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "rb") as f:
            user_topics, last_active = pickle.load(f)
        logging.info("State loaded.")

load_state()

# --------------------- FASTAPI APP -------------------------

app = FastAPI()

# ---------- Webhook handler ----------
@app.post("/webhook")
async def webhook(request: Request):
    if request.headers.get("X-Telegram-Bot-Api-Secret-Token") != WEBHOOK_SECRET:
        return JSONResponse({"status": "forbidden"}, status_code=403)

    data = await request.json()
    update = Update.de_json(data, bot)
    await process_update(update)
    return JSONResponse({"status": "ok"})

# ---------- MAIN UPDATE ROUTER ----------
async def process_update(update: Update):
    if update.message:
        await handle_user_message(update)
    elif update.message is None and update.channel_post is None:
        logging.info("Other update ignored.")

# ---------------- USER → ADMIN -----------------
async def handle_user_message(update: Update):
    user = update.message.from_user
    text = update.message.text or ""

    last_active[user.id] = datetime.now()

    try:
        if user.id not in user_topics:
            topic = await bot.create_forum_topic(
                chat_id=FORUM_CHAT_ID,
                name=f"{user.first_name}"
            )
            user_topics[user.id] = topic.message_thread_id
            save_state()

        thread_id = user_topics[user.id]

        await bot.send_message(
            chat_id=FORUM_CHAT_ID,
            message_thread_id=thread_id,
            text=f"📩 *Сообщение от {user.first_name}:*\n{text}",
            parse_mode="Markdown"
        )

        await update.message.reply_text("💌 Сообщение отправлено администратору!")

    except Exception as e:
        logging.error(f"Send error: {e}")
        await update.message.reply_text("⚠ Произошла ошибка отправки")


# ---------------- ADMIN → USER -----------------
@app.post("/admin-reply")
async def admin_reply(request: Request):
    data = await request.json()
    update = Update.de_json(data, bot)
    message = update.message

    if not message or not message.is_topic_message:
        return {"ok": True}

    text = message.text
    thread_id = message.message_thread_id

    user_id = next((uid for uid, tid in user_topics.items() if tid == thread_id), None)

    if not user_id:
        await bot.send_message(FORUM_CHAT_ID, "❌ Пользователь не найден.", message_thread_id=thread_id)
        return {"ok": True}

    try:
        await bot.send_message(
            chat_id=user_id,
            text=f"💬 Ответ администратора:\n{text}"
        )
    except Exception as e:
        await bot.send_message(
            chat_id=FORUM_CHAT_ID,
            message_thread_id=thread_id,
            text="❌ Пользователь недоступен."
        )
        logging.error(e)

    return {"ok": True}


# ------------------- ROOT --------------------
@app.get("/")
def home():
    return {"status": "running"}
