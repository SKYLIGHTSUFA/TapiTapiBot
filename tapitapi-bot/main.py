import asyncio
import logging
from aiogram import Bot, Dispatcher
from bot.config import BOT_TOKEN
from bot.handlers import start, registration, receipt, tickets, support, admin
from bot.handlers.web_admin import start_web_admin
from bot.models.database import init_db
from bot.services.lottery_scheduler import init_scheduler

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


async def main():
    logging.basicConfig(level=logging.INFO)
    await init_db()
    dp.include_router(start.router)
    dp.include_router(registration.router)
    dp.include_router(receipt.router)
    dp.include_router(tickets.router)
    dp.include_router(support.router)
    dp.include_router(admin.router)

    asyncio.create_task(start_web_admin())
    init_scheduler()

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())