"""
Main application launcher for Canva Distribution System.
Runs the Telegram Bot and the FastAPI Admin Dashboard concurrently in a production-ready setup.
"""

import os
import sys
import threading
import logging
import time
import uvicorn

from config import settings
import database as db
from bot import bot, setup_bot_commands
from dashboard import app

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("canva_system")


def run_telegram_bot():
    """Starts Telegram Bot polling with automatic reconnection."""
    logger.info("Starting Telegram Bot polling...")
    if not settings.BOT_TOKEN:
        logger.warning("BOT_TOKEN is not configured! Bot polling will not start until BOT_TOKEN is provided in .env.")
        return

    while True:
        try:
            bot_info = bot.get_me()
            logger.info(f"Connected to Telegram as @{bot_info.username} (ID: {bot_info.id})")
            setup_bot_commands()
            bot.infinity_polling(timeout=20, long_polling_timeout=20)
        except Exception as e:
            logger.error(f"Telegram polling encountered an error: {e}. Reconnecting in 5 seconds...")
            time.sleep(5)


def run_web_dashboard():
    """Runs FastAPI web server with Uvicorn."""
    # Use environment PORT if set (Render / Railway requirement)
    port = int(os.environ.get("PORT", settings.PORT))
    host = settings.HOST
    logger.info(f"Starting FastAPI Web Dashboard on http://{host}:{port}")
    uvicorn.run(app, host=host, port=port, log_level="info")


def main():
    """Initializes database and orchestrates bot and dashboard services."""
    logger.info("Initializing SQLite database...")
    db.init_db()
    
    stats = db.get_system_stats()
    logger.info(
        f"Database initialized. Current status: {stats['claimed_seats']}/{settings.MAX_SEATS} seats taken "
        f"({stats['remaining_seats']} seats remaining)."
    )

    # Launch Telegram Bot in background daemon thread
    bot_thread = threading.Thread(target=run_telegram_bot, name="TelegramBotThread", daemon=True)
    bot_thread.start()

    # Run FastAPI web dashboard in main thread (binds port for cloud hosts like Render/Railway)
    run_web_dashboard()


if __name__ == "__main__":
    main()
