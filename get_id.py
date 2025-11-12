from __future__ import annotations
import logging
from typing import Dict, Set, Optional
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Message, ForumTopic
from telegram.constants import ParseMode, ChatType
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

# ===================== НАСТРОЙКИ =====================
TOKEN = "8560878728:AAEA6FjMH4dt3auCxb1SLat7gOP1J0JWrVM"
FORUM_CHAT_ID = -1003363764646
ADMIN_IDS = {5093176369}  # твой ID
# =====================================================

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

user_to_thread: Dict[int, int] = {}
thread_to_user: Dict[int, int] = {}
banned_users: Set[int] = set()

START_TEXT = (
    "Приветик, солнце! Этот бот — для общения и поддержки: если скучно или хочешь "
    "поделиться проблемами — мы рядом и поможем тебе! 💛\n\n"
    "Админы — живые люди, относись с уважением. Если не отвечают, продублируй сообщение "
    "или тегни админа из списка в тгк, прояви терпение!\n\n"
    "*Перед началом общения ознакомься с правилами:*\n"
    "• не спамь\n"
    "• не оскорбляй админов\n"
    "• не делись юзом и ссылками на другие соцсети\n"
    "• не присылай контент 18+\n"
    "• не меняй админа больше 3 раз подряд\n"
    "• не проси админа нарушать правила\n\n"
    "наш бот анкет — @BloodyFortuneBot\n\n"
    "Приятного общения!"
)

RULES_TEXT = (
    "Правила кратко:\n"
    "• без спама, оскорблений и 18+\n"
    "• не делимся юзом и ссылками на сторонние соцсети\n"
    "• админа не меняем более 3 раз подряд\n"
    "• просьбы нарушать правила — игнорируются\n"
)

def is_admin(uid: int) -> bool:
    return uid in ADMIN_IDS

def not_banned(uid: int) -> bool:
    return uid not in banned_users

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("Правила", callback_data="rules")]])
    await update.effective_message.reply_text(
        START_TEXT, parse_mode=ParseMode.MARKDOWN, reply_markup=kb
    )

async def on_rules_btn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await q.message.reply_text(RULES_TEXT)

async def ensure_topic_for_user(user_id: int, title: str, context: ContextTypes.DEFAULT_TYPE) -> int:
    if user_id in user_to_thread:
        return user_to_thread[user_id]
    name = (title or "Пользователь").strip()
    if len(name) > 64:
        name = name[:61] + "..."
    name = f"{name} • {user_id}"
    topic: ForumTopic = await context.bot.create_forum_topic(chat_id=FORUM_CHAT_ID, name=name)
    thread_id = topic.message_thread_id
    user_to_thread[user_id] = thread_id
    thread_to_user[thread_id] = user_id
    await context.bot.send_message(
        chat_id=FORUM_CHAT_ID,
        message_thread_id=thread_id,
        text=f"Создана тема для пользователя `{user_id}`.",
        parse_mode=ParseMode.MARKDOWN,
    )
    return thread_id

async def pipe_user_to_forum(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg: Message = update.effective_message
    user = msg.from_user
    if not user or user.is_bot or not not_banned(user.id):
        return
    thread_id = await ensure_topic_for_user(user.id, user.full_name, context)
    header = f"🆕 Сообщение от {user.full_name}\n• ID: `{user.id}`\n• @{user.username or 'без юзера'}"
    copied = await context.bot.copy_message(
        chat_id=FORUM_CHAT_ID,
        message_thread_id=thread_id,
        from_chat_id=msg.chat_id,
        message_id=msg.message_id,
    )
    await context.bot.send_message(
        chat_id=FORUM_CHAT_ID,
        message_thread_id=thread_id,
        text=header,
        parse_mode=ParseMode.MARKDOWN,
        reply_to_message_id=copied.message_id
    )
    await msg.reply_text("Отправила твоё сообщение админам 💌. Подожди немного, тебе ответят.")

async def forum_to_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    chat = update.effective_chat
    if chat.id != FORUM_CHAT_ID or not msg.message_thread_id:
        return
    if not msg.from_user or not is_admin(msg.from_user.id):
        return
    target_user_id: Optional[int] = thread_to_user.get(msg.message_thread_id)
    if not target_user_id:
        return
    await context.bot.copy_message(
        chat_id=target_user_id,
        from_chat_id=chat.id,
        message_id=msg.message_id,
    )

async def ban_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not (update.effective_user and is_admin(update.effective_user.id)):
        return
    msg = update.effective_message
    target_id = None
    if context.args:
        try:
            target_id = int(context.args[0])
        except ValueError:
            await msg.reply_text("Использование: /ban <user_id>")
            return
    if target_id is None and msg.message_thread_id:
        target_id = thread_to_user.get(msg.message_thread_id)
    if target_id is None:
        await msg.reply_text("Не нашёл пользователя.")
        return
    banned_users.add(target_id)
    await msg.reply_text(f"Пользователь {target_id} забанен.")
    try:
        await context.bot.send_message(chat_id=target_id, text="Тебе ограничен доступ к боту.")
    except Exception:
        pass

async def unban_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not (update.effective_user and is_admin(update.effective_user.id)):
        return
    msg = update.effective_message
    target_id = None
    if context.args:
        try:
            target_id = int(context.args[0])
        except ValueError:
            await msg.reply_text("Использование: /unban <user_id>")
            return
    if target_id is None and msg.message_thread_id:
        target_id = thread_to_user.get(msg.message_thread_id)
    if target_id is None:
        await msg.reply_text("Не нашёл пользователя.")
        return
    banned_users.discard(target_id)
    await msg.reply_text(f"Пользователь {target_id} разбанен.")
    try:
        await context.bot.send_message(chat_id=target_id, text="Доступ к боту восстановлен.")
    except Exception:
        pass

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ban", ban_cmd))
    app.add_handler(CommandHandler("unban", unban_cmd))
    app.add_handler(CallbackQueryHandler(on_rules_btn, pattern="^rules$"))
    app.add_handler(MessageHandler(filters.Chat(FORUM_CHAT_ID) & ~filters.COMMAND, forum_to_user))
    app.add_handler(MessageHandler(filters.ChatType.PRIVATE & ~filters.COMMAND, pipe_user_to_forum))
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
