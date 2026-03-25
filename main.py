import logging

from telegram import BotCommand
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters

from bot.config import BOT_TOKEN
from bot.handlers import (
    clear_clipboard_handler,
    clipboard_handler,
    health_handler,
    help_handler,
    hibernate_handler,
    logs_handler,
    menu_handler,
    ping_handler,
    screenshot_handler,
    shutdown_handler,
    sleep_handler,
    start_comfy_handler,
    start_handler,
    stats_handler,
    status_handler,
    stop_comfy_handler,
    tasks_handler,
    text_router,
    voice_handler,
    volume_handler,
    wake_handler,
    wake_wait_handler,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)


async def post_init(application):
    commands = [
        BotCommand("start", "open the control panel"),
        BotCommand("menu", "show the keyboard again"),
        BotCommand("help", "show available commands"),
        BotCommand("wake", "send Wake-on-LAN packet"),
        BotCommand("wakewait", "wake the PC and wait until agent is online"),
        BotCommand("status", "check host status"),
        BotCommand("health", "show agent info"),
        BotCommand("screen", "take a screenshot"),
        BotCommand("clipboard", "show clipboard history"),
        BotCommand("clearclip", "clear clipboard history"),
        BotCommand("stats", "show cpu/ram/disk usage"),
        BotCommand("logs", "show recent agent logs"),
        BotCommand("tasks", "show managed tasks"),
        BotCommand("startcomfy", "start managed ComfyUI"),
        BotCommand("stopcomfy", "stop managed ComfyUI"),
        BotCommand("volume", "show current volume"),
        BotCommand("sleep", "put the PC to sleep"),
        BotCommand("hibernate", "hibernate the PC"),
        BotCommand("shutdown", "shutdown the PC"),
        BotCommand("ping", "check whether the bot is alive"),
    ]
    await application.bot.set_my_commands(commands)


def main():
    if not BOT_TOKEN:
        print("Error: BOT_TOKEN is missing in .env")
        return

    application = ApplicationBuilder().token(BOT_TOKEN).post_init(post_init).build()

    command_handlers = {
        "start": start_handler,
        "menu": menu_handler,
        "help": help_handler,
        "wake": wake_handler,
        "wakewait": wake_wait_handler,
        "ping": ping_handler,
        "status": status_handler,
        "health": health_handler,
        "shutdown": shutdown_handler,
        "sleep": sleep_handler,
        "hibernate": hibernate_handler,
        "clipboard": clipboard_handler,
        "clearclip": clear_clipboard_handler,
        "screen": screenshot_handler,
        "screenshot": screenshot_handler,
        "stats": stats_handler,
        "logs": logs_handler,
        "tasks": tasks_handler,
        "startcomfy": start_comfy_handler,
        "stopcomfy": stop_comfy_handler,
        "volume": volume_handler,
    }

    for command, handler in command_handlers.items():
        application.add_handler(CommandHandler(command, handler))

    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_router))
    application.add_handler(MessageHandler(filters.VOICE, voice_handler))

    print("Bot is polling...")
    application.run_polling()


if __name__ == "__main__":
    main()
