import os
import subprocess
import platform
import requests
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ContextTypes
from bot.config import ALLOWED_USERS, TARGET_MAC, TARGET_HOST, AGENT_PORT
from bot.wol import wake

AGENT_URL = f"http://{TARGET_HOST}:{AGENT_PORT}"

def is_allowed(user_id: int) -> bool:
    return user_id in ALLOWED_USERS

def get_keyboard():
    keyboard = [
        [KeyboardButton("🚀 Wake"), KeyboardButton("🛑 Shutdown")],
        [KeyboardButton("📋 Clipboard"), KeyboardButton("🔍 Status")],
        [KeyboardButton("ℹ️ Help"), KeyboardButton("🏓 Ping")]
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
        "👋 **Control Center Online**\n\nI can help you manage your PC remotely.",
        parse_mode="Markdown",
        reply_markup=get_keyboard()
    )

async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_permissions(update):
        return
    help_text = (
        "🤖 **Control Panel Commands:**\n\n"
        "🚀 **Wake** - Send generic Wake-on-LAN packet\n"
        "🛑 **Shutdown** - Remote system shutdown (Requires Agent)\n"
        "📋 **Clipboard** - View last 5 copied items (Requires Agent)\n"
        "🔍 **Status** - Check network connectivity\n"
        "🏓 **Ping** - Check bot latency"
    )
    await update.message.reply_text(help_text, parse_mode="Markdown", reply_markup=get_keyboard())

async def status_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_permissions(update):
        return
    
    await update.message.reply_text("🔍 Checking connectivity...")
    
    # 1. ICMP Ping
    param = '-n' if platform.system().lower() == 'windows' else '-c'
    command = ['ping', param, '1', TARGET_HOST]
    try:
        response = subprocess.call(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        is_online = response == 0
    except Exception:
        is_online = False

    status_msg = "🟢 **Online**" if is_online else "🔴 **Offline**"
    
    # 2. Agent Check (if online)
    agent_msg = ""
    if is_online:
        try:
            r = requests.get(f"{AGENT_URL}/ping", timeout=2)
            if r.status_code == 200:
                agent_msg = "\n🤖 **Agent:** Connected ✅"
            else:
                agent_msg = "\n🤖 **Agent:** Error ⚠️"
        except:
            agent_msg = "\n🤖 **Agent:** Unreachable ❌"

    await update.message.reply_text(
        f"🖥️ **PC Status:** {status_msg}{agent_msg}", 
        parse_mode="Markdown",
        reply_markup=get_keyboard()
    )

async def wake_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_permissions(update):
        return

    wake(TARGET_MAC)
    await update.message.reply_text("🚀 **Magic Packet Sent!**\nWaiting for PC to wake up...", parse_mode="Markdown", reply_markup=get_keyboard())

async def shutdown_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_permissions(update):
        return
    
    await update.message.reply_text("🛑 Sending shutdown command...", reply_markup=get_keyboard())
    try:
        r = requests.post(f"{AGENT_URL}/shutdown", timeout=3)
        if r.status_code == 200:
            await update.message.reply_text("✅ **Shutdown Initiated**\nSystem is powering off.", parse_mode="Markdown")
        else:
            await update.message.reply_text(f"⚠️ **Error:** Agent returned {r.status_code}", parse_mode="Markdown")
    except requests.exceptions.RequestException:
        await update.message.reply_text("❌ **Failed:** Agent unreachable.\nIs the PC on and Agent running?", parse_mode="Markdown")

async def clipboard_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_permissions(update):
        return
    
    try:
        r = requests.get(f"{AGENT_URL}/clipboard", timeout=3)
        if r.status_code == 200:
            history = r.json().get("history", [])
            if not history:
                content = "📋 **Clipboard is empty**"
            else:
                content = "📋 **Clipboard History:**\n\n" + "\n\n".join([f"🔹 `{item}`" for item in history])
            await update.message.reply_text(content, parse_mode="Markdown", reply_markup=get_keyboard())
        else:
            await update.message.reply_text(f"⚠️ **Error:** Agent returned {r.status_code}", parse_mode="Markdown")
    except requests.exceptions.RequestException:
        if update.effective_message:
            await update.effective_message.reply_text("❌ **Failed:** Agent unreachable.", parse_mode="Markdown")

async def ping_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_permissions(update):
        return
    await update.message.reply_text("🏓 **Pong!** Bot is active.", parse_mode="Markdown", reply_markup=get_keyboard())
