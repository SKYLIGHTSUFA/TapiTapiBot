from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command
from bot.config import ADMIN_IDS
from bot.models.database import AsyncSessionLocal, User, Ticket, Draw, TicketStatus
from bot.services.audit import log_action
from sqlalchemy import select, func

router = Router()

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

@router.message(Command("admin"))
async def admin_panel(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("Нет доступа.")
        return
    async with AsyncSessionLocal() as session:
        users_count = await session.scalar(select(func.count()).select_from(User))
        tickets_count = await session.scalar(select(func.count()).select_from(Ticket))
        active_tickets = await session.scalar(select(func.count()).select_from(Ticket).where(Ticket.status == TicketStatus.ACTIVE))
        draws_count = await session.scalar(select(func.count()).select_from(Draw))
    text = (
        f"📊 Статистика:\n"
        f"Пользователей: {users_count}\n"
        f"Всего билетов: {tickets_count}\n"
        f"Активных билетов: {active_tickets}\n"
        f"Проведено розыгрышей: {draws_count}\n\n"
        "Доступные команды:\n"
        "/admin_cancel_ticket <код> – аннулировать билет"
    )
    await message.answer(text)

@router.message(Command("admin_cancel_ticket"))
async def cancel_ticket(message: Message):
    if not is_admin(message.from_user.id):
        return
    parts = message.text.split()
    if len(parts) != 2:
        await message.answer("Используйте: /admin_cancel_ticket <код_билета>")
        return
    code = parts[1]
    async with AsyncSessionLocal() as session:
        ticket = await session.execute(select(Ticket).where(Ticket.code == code))
        ticket = ticket.scalar_one_or_none()
        if not ticket:
            await message.answer("Билет не найден.")
            return
        ticket.status = TicketStatus.CANCELLED
        await session.commit()
    await log_action("ticket_cancelled", message.from_user.id, {"ticket": code})
    await message.answer(f"Билет {code} аннулирован.")