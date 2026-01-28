import asyncio
import logging
import os
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

load_dotenv()

import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.core.settings')
django.setup()

from bot.handlers import routers
from bot.middleware import StudentMentorCheckMiddleware

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv('BOT_TOKEN')


async def main():
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())

    # Add middleware to check student-mentor assignment
    dp.message.middleware(StudentMentorCheckMiddleware())
    dp.callback_query.middleware(StudentMentorCheckMiddleware())

    for router in routers:
        dp.include_router(router)

    print("Bot is running...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
