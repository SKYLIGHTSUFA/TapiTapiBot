from aiogram import Router
from aiogram.types import Message
from aiogram.filters import CommandStart
from bot.keyboards.inline import agreement_keyboard

router = Router()

@router.message(CommandStart())
async def cmd_start(message: Message):
    from bot.models.database import AsyncSessionLocal, User
    async with AsyncSessionLocal() as session:
        user = await session.get(User, message.from_user.id)
        if user:
            await message.answer(
                f"С возвращением!\n"
                "Загружайте чеки и участвуйте в розыгрышах.\n"
                "/mytickets – ваши билеты\n"
                "/support – помощь"
            )
        else:
            rules = (
                "📜 *Правила акции «Тапитапи»*\n\n"
                "1. Купите вино «Тапитапи».\n"
                "2. Загрузите фото чека.\n"
                "3. Получите билет.\n"
                "4. Розыгрыши: каждый пн 12:00 (2 серт. Ozon 2000₽), "
                "каждый первый пн месяца (5 серт.), 21.12.2026 – главные призы.\n"
                "5. Чем больше чеков – тем выше шанс.\n\n"
                "Для участия дайте согласие на обработку данных."
            )
            await message.answer(rules, parse_mode="Markdown", reply_markup=agreement_keyboard())