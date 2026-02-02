from telegram.ext import ApplicationBuilder, CommandHandler
from bot.handlers import wake_handler, ping_handler, start_handler, help_handler, status_handler
from bot.config import BOT_TOKEN

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(CommandHandler("help", help_handler))
    app.add_handler(CommandHandler("wake", wake_handler))
    app.add_handler(CommandHandler("ping", ping_handler))
    app.add_handler(CommandHandler("status", status_handler))

    app.run_polling()

if __name__ == "__main__":
    main()
