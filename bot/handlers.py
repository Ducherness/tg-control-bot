import os
import subprocess
import platform
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ContextTypes
from bot.config import ALLOWED_USERS, TARGET_MAC, TARGET_HOST
from bot.wol import wake

def is_allowed(user_id: int) -> bool:
    return user_id in ALLOWED_USERS

def get_keyboard():
    keyboard = [
        [KeyboardButton("/wake"), KeyboardButton("/status")],
        [KeyboardButton("/ping"), KeyboardButton("/help")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

async def check_permissions(update: Update) -> bool:
    if not is_allowed(update.effective_user.id):
        await update.message.reply_text("⛔ Access denied")
        return False
    return True

async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_permissions(update):
        return
    await update.message.reply_text(
        "👋 Welcome! I can help you control your PC.\nUse the buttons below:",
        reply_markup=get_keyboard()
    )

async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_permissions(update):
        return
    help_text = (
        "🤖 **Available Commands:**\n\n"
        "🟢 */wake* - Wake up the PC (WoL)\n"
        "🔍 */status* - Check if PC is online\n"
        "🏓 */ping* - Check bot latency\n"
        "ℹ️ */help* - Show this message"
    )
    await update.message.reply_text(help_text, parse_mode="Markdown", reply_markup=get_keyboard())

async def status_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_permissions(update):
        return
    
    await update.message.reply_text("🔍 Checking PC status...")
    
    param = '-n' if platform.system().lower() == 'windows' else '-c'
    command = ['ping', param, '1', TARGET_HOST]
    
    try:
        response = subprocess.call(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        is_online = response == 0
    except Exception:
        is_online = False

    status_msg = "🟢 Online" if is_online else "🔴 Offline"
    await update.message.reply_text(f"🖥️ PC Status: {status_msg}", reply_markup=get_keyboard())

async def wake_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_permissions(update):
        return

    wake(TARGET_MAC)
    await update.message.reply_text("🟢 Magic packet sent! 🚀", reply_markup=get_keyboard())

async def ping_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_permissions(update):
        return
    await update.message.reply_text("🏓 Pong! I'm here.", reply_markup=get_keyboard())
