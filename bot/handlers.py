from telegram import Update
from telegram.ext import ContextTypes
from bot.config import ALLOWED_USERS, TARGET_MAC
from bot.wol import wake

def is_allowed(user_id: int) -> bool:
    return user_id in ALLOWED_USERS

async def wake_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update.effective_user.id):
        await update.message.reply_text("⛔ Access denied")
        return

    wake(TARGET_MAC)
    await update.message.reply_text("🟢 Magic packet отправлен")

async def ping_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🤖 Bot online")
