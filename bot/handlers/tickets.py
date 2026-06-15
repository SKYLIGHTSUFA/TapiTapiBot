from aiogram import F, Router
from aiogram.types import CallbackQuery, Message
from aiogram.filters import Command
from datetime import datetime
from bot.models.database import AsyncSessionLocal, PrizeDelivery, Ticket, TicketStatus
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


@router.callback_query(F.data.startswith("confirm_prize:"))
async def confirm_prize(callback: CallbackQuery):
    delivery_id = int(callback.data.split(":", 1)[1])
    async with AsyncSessionLocal() as session:
        delivery = await session.get(PrizeDelivery, delivery_id)
        if not delivery or delivery.telegram_id != callback.from_user.id:
            await callback.answer("Приз не найден", show_alert=True)
            return
        if delivery.status == "expired":
            await callback.answer("Срок подтверждения истёк", show_alert=True)
            return
        if delivery.status == "confirmed":
            await callback.answer("Уже подтверждено")
            return

        delivery.status = "confirmed"
        delivery.responded_at = datetime.utcnow()
        await session.commit()

        if delivery.prize_type == "ozon":
            await callback.message.answer(
                f"✅ Получение подтверждено.\n"
                f"Код сертификата Ozon: `{delivery.prize_code}`\n"
                "Активация: Ozon → Активация подарочной карты."
            )
        else:
            await callback.message.answer(
                "✅ Получение подтверждено.\n"
                "Для оформления главного приза отправьте в поддержку ФИО, адрес и телефон."
            )
    await callback.answer("Подтверждено")