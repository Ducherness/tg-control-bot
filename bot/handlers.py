import os
import subprocess
import platform
import httpx
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ContextTypes
from bot.config import ALLOWED_USERS, TARGET_MAC, TARGET_HOST, AGENT_PORT
from bot.wol import wake
from bot.voice import speech_to_text
from bot.ai import parse_intent
from telegram.ext import MessageHandler, filters

AGENT_URL = f"http://{TARGET_HOST}:{AGENT_PORT}"

def is_allowed(user_id: int) -> bool:
    return user_id in ALLOWED_USERS

def get_keyboard():
    keyboard = [
        [KeyboardButton("🚀 Wake"), KeyboardButton("🛑 Shutdown")],
        [KeyboardButton("📸 Screen"), KeyboardButton("📋 Clipboard")],
        [KeyboardButton("📊 Stats"), KeyboardButton("🔊 Volume")],
        [KeyboardButton("🔍 Status"), KeyboardButton("ℹ️ Help")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

async def check_permissions(update: Update) -> bool:
    if not is_allowed(update.effective_user.id):
        await update.effective_message.reply_text("⛔ Access denied")
        return False
    return True

async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_permissions(update):
        return
    await update.effective_message.reply_text(
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
        "📸 **Screen** - Capture remote screen (Requires Agent)\n"
        "📋 **Clipboard** - View last 5 copied items (Requires Agent)\n"
        "📊 **Stats** - View system CPU/RAM usage (Requires Agent)\n"
        "🔊 **Volume** - Control system volume (Requires Agent)\n"
        "🔍 **Status** - Check network connectivity\n"
        "🏓 **Ping** - Check bot latency"
    )
    await update.effective_message.reply_text(help_text, parse_mode="Markdown", reply_markup=get_keyboard())

async def status_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_permissions(update):
        return
    
    await update.effective_message.reply_text("🔍 Checking connectivity...")
    
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
            async with httpx.AsyncClient(timeout=2.0) as client:
                r = await client.get(f"{AGENT_URL}/ping")
                if r.status_code == 200:
                    agent_msg = "\n🤖 **Agent:** Connected ✅"
                else:
                    agent_msg = "\n🤖 **Agent:** Error ⚠️"
        except Exception:
            agent_msg = "\n🤖 **Agent:** Unreachable ❌"

    await update.effective_message.reply_text(
        f"🖥️ **PC Status:** {status_msg}{agent_msg}", 
        parse_mode="Markdown",
        reply_markup=get_keyboard()
    )

async def wake_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_permissions(update):
        return

    wake(TARGET_MAC)
    await update.effective_message.reply_text("🚀 **Magic Packet Sent!**\nWaiting for PC to wake up...", parse_mode="Markdown", reply_markup=get_keyboard())

async def shutdown_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_permissions(update):
        return
    
    await update.effective_message.reply_text("🛑 Sending shutdown command...", reply_markup=get_keyboard())
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            r = await client.post(f"{AGENT_URL}/shutdown")
            if r.status_code == 200:
                await update.effective_message.reply_text("✅ **Shutdown Initiated**\nSystem is powering off.", parse_mode="Markdown")
            else:
                await update.effective_message.reply_text(f"⚠️ **Error:** Agent returned {r.status_code}", parse_mode="Markdown")
    except Exception:
        await update.effective_message.reply_text("❌ **Failed:** Agent unreachable.\nIs the PC on and Agent running?", parse_mode="Markdown")

async def clipboard_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_permissions(update):
        return
    
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            r = await client.get(f"{AGENT_URL}/clipboard")
            if r.status_code == 200:
                history = r.json().get("history", [])
                if not history:
                    content = "📋 **Clipboard is empty**"
                else:
                    content = "📋 **Clipboard History:**\n\n" + "\n\n".join([f"🔹 `{item}`" for item in history])
                await update.effective_message.reply_text(content, parse_mode="Markdown", reply_markup=get_keyboard())
            else:
                await update.effective_message.reply_text(f"⚠️ **Error:** Agent returned {r.status_code}", parse_mode="Markdown")
    except Exception:
        await update.effective_message.reply_text("❌ **Failed:** Agent unreachable.", parse_mode="Markdown")

async def screenshot_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_permissions(update):
        return
    
    await update.effective_message.reply_chat_action("upload_photo")
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(f"{AGENT_URL}/screenshot")
            if r.status_code == 200:
                await update.effective_message.reply_photo(r.content, caption="📸 **Screenshot**", reply_markup=get_keyboard())
            else:
                await update.effective_message.reply_text(f"⚠️ **Error:** Agent returned {r.status_code}")
    except Exception:
        await update.effective_message.reply_text("❌ **Failed:** Agent unreachable.")

async def stats_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_permissions(update):
        return
    
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            r = await client.get(f"{AGENT_URL}/stats")
            if r.status_code == 200:
                data = r.json()
                msg = (
                    f"📊 **System Stats**\n\n"
                    f"🧠 **CPU:** {data['cpu']}%\n"
                    f"💾 **RAM:** {data['ram_percent']}% ({data['ram_used_gb']}GB / {data['ram_total_gb']}GB)\n"
                    f"💿 **Disk:** {data['disk_percent']}% (Free: {data['disk_free_gb']}GB)"
                )
                await update.effective_message.reply_text(msg, parse_mode="Markdown", reply_markup=get_keyboard())
            else:
                await update.effective_message.reply_text(f"⚠️ **Error:** Agent returned {r.status_code}")
    except Exception:
        await update.effective_message.reply_text("❌ **Failed:** Agent unreachable.")

async def volume_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_permissions(update):
        return

    # Check for arguments: /volume + /volume - /volume mute
    # Or text "Volume +", "Volume -", "Mute"
    # For now, just show current volume and simple toggle? 
    # Let's make it interactive or just simple commands if text router supports it.
    
    # Simple implementation: Show volume and instructions or handle if text has args
    # But since we are button based, maybe we can't easily do args unless we add more buttons.
    # Let's just do a fetch of volume for now.
    
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            r = await client.post(f"{AGENT_URL}/volume", json={"action": "get"})
            if r.status_code == 200:
                data = r.json()
                vol_status = "🔇 Muted" if data['muted'] else f"🔊 {data['level']}%"
                
                # We can send a message with inline buttons? 
                # For simplicity, stick to text.
                await update.effective_message.reply_text(
                    f"🔊 **Volume:** {vol_status}\n\n"
                    "reply with `+` to increase, `-` to decrease, or `mute` to toggle.", 
                    parse_mode="Markdown",
                    reply_markup=get_keyboard()
                )
            else:
                await update.effective_message.reply_text(f"⚠️ **Error:** Agent returned {r.status_code}")
    except Exception:
        await update.effective_message.reply_text("❌ **Failed:** Agent unreachable.")

# We need a way to handle volume commands if we preserve the "reply with +" idea.
# But for now, let's just stick to the main handlers.  


async def ping_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_permissions(update):
        return
    await update.effective_message.reply_text("🏓 **Pong!** Bot is active.", parse_mode="Markdown", reply_markup=get_keyboard())

async def text_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.effective_message.text

    if text == "🚀 Wake":
        await wake_handler(update, context)
    elif text == "🛑 Shutdown":
        await shutdown_handler(update, context)
    elif text == "📋 Clipboard":
        await clipboard_handler(update, context)
    elif text == "📸 Screen":
        await screenshot_handler(update, context)
    elif text == "📊 Stats":
        await stats_handler(update, context)
    elif text == "🔊 Volume":
        await volume_handler(update, context)
    elif text == "🔍 Status":
        await status_handler(update, context)
    elif text == "🏓 Ping":
        await ping_handler(update, context)
    elif text == "ℹ️ Help":
        await help_handler(update, context)
    elif text in ["+", "-", "mute"]: # Simple volume controls
        # Determine action
        action = "get"
        level_change = 0.0
        
        if text == "mute":
            action = "mute"
        elif text == "+":
            action = "set"
            level_change = 0.1
        elif text == "-":
            action = "set"
            level_change = -0.1
            
        # We need current volume to add/subtract? 
        # Actually agent 'set' expects absolute level.
        # So we need to 'get' then 'set'.
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                # First get current
                r = await client.post(f"{AGENT_URL}/volume", json={"action": "get"})
                if r.status_code == 200:
                    current_data = r.json()
                    current_level = float(current_data['level']) / 100.0
                    
                    if action == "mute":
                         r2 = await client.post(f"{AGENT_URL}/volume", json={"action": "mute"})
                         new_status = r2.json()
                         await update.effective_message.reply_text(f"🔊 **Volume:** {new_status['status']}")
                    elif action == "set":
                        new_level = current_level + level_change
                        r2 = await client.post(f"{AGENT_URL}/volume", json={"action": "set", "level": new_level})
                        new_data = r2.json()
                        await update.effective_message.reply_text(f"🔊 **Volume:** {int(new_data['level'] * 100)}%")
        except Exception:
             await update.effective_message.reply_text("❌ **Failed:** Agent unreachable.")
        return
    else:
        await update.effective_message.reply_text(
            "❓ Unknown command",
            reply_markup=get_keyboard()
        )

async def voice_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_permissions(update):
        return

    voice = update.message.voice
    file = await context.bot.get_file(voice.file_id)

    audio_path = f"/tmp/{voice.file_id}.ogg"
    await file.download_to_drive(audio_path)

    await update.effective_message.reply_text("🎧 Processing voice command...")

    try:
        text = await speech_to_text(audio_path)
        intent = await parse_intent(text)

        action = intent.get("action", "unknown")

        if action == "wake":
            await wake_handler(update, context)
            msg = "🧠 **Action:** Wake PC"

        elif action == "shutdown":
            await shutdown_handler(update, context)
            msg = "🧠 **Action:** Shutdown PC"

        elif action == "sleep":
            await sleep_handler(update, context)
            msg = "🧠 **Action:** Sleep PC"

        elif action == "status":
            await status_handler(update, context)
            return

        elif action == "ping":
            await ping_handler(update, context)
            return

        else:
            msg = "❓ **Unknown command**"

        await update.effective_message.reply_text(
            f"{msg}\n\n🗣 **You said:** `{text}`",
            parse_mode="Markdown",
            reply_markup=get_keyboard()
        )

    finally:
        if os.path.exists(audio_path):
            os.remove(audio_path)
