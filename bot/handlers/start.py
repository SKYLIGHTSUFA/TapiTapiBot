from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import CommandStart
from bot.keyboards.inline import agreement_keyboard
from bot.keyboards.menu import main_menu
from datetime import datetime, timedelta
import pytz
from bot.config import MAIN_DRAW_DATE

router = Router()

@router.message(CommandStart())
async def cmd_start(message: Message):
    from bot.models.database import AsyncSessionLocal, User
    async with AsyncSessionLocal() as session:
        user = await session.get(User, message.from_user.id)
        if user:
            await message.answer("Главное меню:", reply_markup=main_menu())
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

@router.message(F.text == "🎫 Мои билеты")
async def my_tickets_button(message: Message):
    from bot.handlers.tickets import show_my_tickets
    await show_my_tickets(message)

@router.message(F.text == "📅 Ближайший розыгрыш")
async def next_draw_button(message: Message):
    now = datetime.now(pytz.timezone("Europe/Moscow"))
    days_ahead = 0 - now.weekday()
    if days_ahead <= 0:
        days_ahead += 7
    next_monday = now + timedelta(days=days_ahead)
    next_monday = next_monday.replace(hour=12, minute=0, second=0, microsecond=0)
    main_date = datetime.strptime(MAIN_DRAW_DATE, "%Y-%m-%d").replace(tzinfo=pytz.timezone("Europe/Moscow"))
    if next_monday.date() == main_date.date():
        msg = f"🏆 Ближайший розыгрыш – ГЛАВНЫЙ! {next_monday.strftime('%d.%m.%Y')} в 12:00. Призы: путешествие в ОАЭ, iPhone, MacBook."
    else:
        msg = f"🎁 Следующий розыгрыш: {next_monday.strftime('%d.%m.%Y')} в 12:00. Призы: сертификаты Ozon 2000₽."
    await message.answer(msg)

@router.message(F.text == "📜 Правила акции")
async def rules_button(message: Message):
    rules = (
        "📜 *Правила акции «Тапитапи»*\n\n"
        "1. Купите вино «Тапитапи».\n"
        "2. Загрузите фото чека.\n"
        "3. Получите билет.\n"
        "4. Розыгрыши: каждый пн 12:00 (2 серт. Ozon 2000₽), "
        "каждый первый пн месяца (5 серт.), 21.12.2026 – главные призы.\n"
        "5. Чем больше чеков – тем выше шанс.\n\n"
        "Для участия необходимо согласие на обработку данных."
    )
    await message.answer(rules, parse_mode="Markdown")

@router.message(F.text == "🆘 Поддержка")
async def support_button(message: Message):
    from bot.handlers.support import support_command
    await support_command(message)
