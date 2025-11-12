from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

TOKEN = "8585263637:AAGaIqSO_EcH-6e9yiSsdptbjNUXBzrsvlQ"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    await update.message.reply_text(f"Chat ID: {chat_id}")

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    print("Бот запущен. Напиши ему /start в Telegram.")
    app.run_polling()

if __name__ == "__main__":
    main()
