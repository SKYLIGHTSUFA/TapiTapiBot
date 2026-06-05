from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command
from bot.models.database import AsyncSessionLocal, Ticket, TicketStatus
from sqlalchemy import select

router = Router()

@router.message(Command("mytickets"))
async def show_my_tickets(message: Message):
    async with AsyncSessionLocal() as session:
        tickets = await session.execute(
            select(Ticket).where(Ticket.telegram_id == message.from_user.id)
        )
        tickets = tickets.scalars().all()
        if not tickets:
            await message.answer("У вас пока нет билетов. Загрузите чек с вином «Тапитапи».")
            return
        active = [t for t in tickets if t.status == TicketStatus.ACTIVE]
        won = [t for t in tickets if t.status == TicketStatus.WON]
        text = f"🎫 Ваши билеты:\n\nАктивных: {len(active)}\nВыигравших: {len(won)}\n"
        if active:
            codes = "\n".join(t.code for t in active[:10])
            text += f"\nПоследние активные:\n{codes}"
        await message.answer(text)