from telegram.ext import ApplicationBuilder, CommandHandler
from bot.handlers import (
    wake_handler, 
    ping_handler, 
    start_handler, 
    help_handler, 
    status_handler,
    shutdown_handler,
    clipboard_handler
)
from bot.config import BOT_TOKEN
from telegram.ext import MessageHandler, filters
from bot.handlers import text_router
import logging


# Basic logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

def main():
    if not BOT_TOKEN:
        print("Error: BOT_TOKEN is missing in .env")
        return

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(CommandHandler("help", help_handler))
    app.add_handler(CommandHandler("wake", wake_handler))
    app.add_handler(CommandHandler("ping", ping_handler))
    app.add_handler(CommandHandler("status", status_handler))
    app.add_handler(CommandHandler("shutdown", shutdown_handler))
    app.add_handler(CommandHandler("clipboard", clipboard_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_router))

    print("Bot is polling...")
    app.run_polling()

if __name__ == "__main__":
    main()
