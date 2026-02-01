import asyncio
import logging
import os
import sys
import signal
import platform
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.storage.redis import RedisStorage

load_dotenv()

import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.core.settings')
django.setup()

from bot.handlers import routers
from bot.middleware import StudentMentorCheckMiddleware, ErrorHandlerMiddleware, ThrottlingMiddleware

# ==================== LOGGING SETUP ====================

# Create logs directory if it doesn't exist
os.makedirs('logs', exist_ok=True)

# Setup structured logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/bot.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

# Configure loggers
aiogram_logger = logging.getLogger('aiogram')
aiogram_logger.setLevel(logging.WARNING)

app_logger = logging.getLogger('studymate')
app_logger.setLevel(logging.INFO)

logger = logging.getLogger(__name__)

# ==================== CONFIGURATION ====================

BOT_TOKEN = os.getenv('BOT_TOKEN')
if not BOT_TOKEN:
    raise ValueError(
        "BOT_TOKEN environment variable is required. "
        "Get it from @BotFather on Telegram"
    )

REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
USE_REDIS = os.getenv('USE_REDIS', 'true').lower() == 'true'

# ==================== MAIN ====================

async def main():
    # Setup storage
    if USE_REDIS:
        try:
            import ssl
            from redis.asyncio import Redis

            # Configure SSL for Heroku Redis (uses self-signed certs)
            if REDIS_URL.startswith('rediss://'):  # SSL Redis (Heroku)
                logger.info("Configuring Redis with SSL for Heroku...")

                # Create SSL context
                ssl_context = ssl.create_default_context()
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_NONE

                # Create Redis client with SSL
                redis_client = Redis.from_url(
                    REDIS_URL,
                    ssl_cert_reqs=None,
                    ssl_check_hostname=False,
                    ssl_ca_certs=None
                )
                storage = RedisStorage(redis=redis_client)
                logger.info("Using RedisStorage with SSL (Heroku)")
            else:
                # Regular Redis without SSL
                storage = RedisStorage.from_url(REDIS_URL)
                logger.info(f"Using RedisStorage: {REDIS_URL}")

        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            logger.warning("Falling back to MemoryStorage (not recommended for production!)")
            storage = MemoryStorage()
    else:
        logger.warning("Using MemoryStorage - FSM state will be lost on restart!")
        storage = MemoryStorage()

    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=storage)

    # Add middlewares (order matters!)
    # 1. Throttling first - prevents spam before processing
    dp.message.middleware(ThrottlingMiddleware(rate_limit=0.5))
    dp.callback_query.middleware(ThrottlingMiddleware(rate_limit=0.3))

    # 2. Error handler - catches all exceptions
    dp.message.middleware(ErrorHandlerMiddleware())
    dp.callback_query.middleware(ErrorHandlerMiddleware())

    # 3. Then business logic middlewares
    dp.message.middleware(StudentMentorCheckMiddleware())
    dp.callback_query.middleware(StudentMentorCheckMiddleware())

    # Include routers
    for router in routers:
        dp.include_router(router)

    logger.info("Bot is starting...")
    logger.info(f"Platform: {platform.system()}")
    logger.info(f"Storage: {type(storage).__name__}")
    logger.info(f"Handlers registered: {len(routers)} routers")

    # Setup graceful shutdown (platform-specific)
    is_windows = platform.system() == 'Windows'

    if not is_windows:
        # Unix-like systems: use signal handlers
        shutdown_event = asyncio.Event()

        def signal_handler(sig):
            logger.info(f"Received signal {sig.name}, initiating graceful shutdown...")
            shutdown_event.set()

        loop = asyncio.get_running_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, lambda s=sig: signal_handler(s))

        try:
            # Start polling in background
            polling_task = asyncio.create_task(dp.start_polling(bot))

            # Wait for shutdown signal
            await shutdown_event.wait()

            logger.info("Stopping polling...")
            polling_task.cancel()

            try:
                await polling_task
            except asyncio.CancelledError:
                pass

        except Exception as e:
            logger.error(f"Error during bot execution: {e}", exc_info=True)
    else:
        # Windows: use try/except for KeyboardInterrupt
        logger.info("Running on Windows - using Ctrl+C for shutdown")
        try:
            await dp.start_polling(bot)
        except asyncio.CancelledError:
            logger.info("Polling cancelled")
        except Exception as e:
            logger.error(f"Error during bot execution: {e}", exc_info=True)

    # Cleanup (common for all platforms)
    logger.info("Closing bot session...")
    await bot.session.close()

    # Close Redis storage if used
    if USE_REDIS and isinstance(storage, RedisStorage):
        try:
            await storage.close()
            logger.info("Redis storage closed")
        except:
            pass

    logger.info("Bot stopped successfully")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
