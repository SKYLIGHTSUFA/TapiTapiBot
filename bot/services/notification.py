import asyncio
from datetime import datetime, timedelta
from bot.dispatcher import bot
from bot.models.database import AsyncSessionLocal, PrizeDelivery, DrawType, Ticket, TicketStatus
from sqlalchemy import select
from bot.services.audit import log_action
from bot.config import END_DATE
from bot.services.lottery_scheduler import perform_draw_with_fns_check

MAX_REDRAWS = 2

async def send_prize_notification(telegram_id: int, ticket_code: str, draw_type: DrawType, draw_id: int):
    if draw_type in (DrawType.WEEKLY, DrawType.MONTHLY):
        import secrets
        prize_code = f"OZON-{secrets.token_hex(8).upper()}"
        async with AsyncSessionLocal() as session:
            delivery = PrizeDelivery(
                telegram_id=telegram_id,
                draw_id=draw_id,
                ticket_code=ticket_code,
                prize_type="ozon",
                prize_code=prize_code,
                status="pending"
            )
            session.add(delivery)
            await session.commit()
        msg = (
            f"🎉 Вы выиграли сертификат Ozon 2000₽!\nКод: `{prize_code}`\n"
            "Активация: Ozon → Активация подарочной карты.\n"
            "Если не получили код в течение часа, обратитесь в поддержку."
        )
        await bot.send_message(telegram_id, msg)
    else:
        # Главный розыгрыш
        await bot.send_message(
            telegram_id,
            "🏆 ГЛАВНЫЙ ПРИЗ! Для получения отправьте в течение 72 часов ФИО, адрес, телефон."
        )
        async with AsyncSessionLocal() as session:
            delivery = PrizeDelivery(
                telegram_id=telegram_id,
                draw_id=draw_id,
                ticket_code=ticket_code,
                prize_type="main",
                status="pending"
            )
            session.add(delivery)
            await session.commit()
        asyncio.create_task(check_winner_response(telegram_id, draw_id, ticket_code, draw_type))

async def check_winner_response(telegram_id: int, draw_id: int, ticket_code: str, draw_type: DrawType):
    await asyncio.sleep(72 * 3600)
    async with AsyncSessionLocal() as session:
        delivery = (await session.execute(
            select(PrizeDelivery).where(
                PrizeDelivery.draw_id == draw_id,
                PrizeDelivery.ticket_code == ticket_code
            )
        )).scalar_one_or_none()
        if delivery and delivery.status == "pending":
            delivery.status = "expired"
            await session.commit()
            await log_action("winner_no_response", telegram_id, {"draw_id": draw_id})
            # Аннулируем билет
            ticket = await session.execute(select(Ticket).where(Ticket.code == ticket_code))
            ticket = ticket.scalar_one_or_none()
            if ticket:
                ticket.status = TicketStatus.CANCELLED
                await session.commit()
            # Считаем количество уже проведённых перерозыгрышей для этого розыгрыша
            redraw_count = await session.scalar(
                select(func.count()).select_from(Draw).where(
                    Draw.draw_type == draw_type,
                    Draw.winners_data.contains({"redraw_of": draw_id})  # упрощённо, лучше отдельным полем
                )
            ) or 0
            if redraw_count < MAX_REDRAWS and datetime.utcnow() < datetime.strptime(END_DATE, "%Y-%m-%d"):
                # Повторный розыгрыш одного приза
                await perform_redraw(draw_type, draw_id)

async def perform_redraw(draw_type: DrawType, original_draw_id: int):
    # Используем существующую функцию, но с одним призом
    # Для этого временно меняем prizes_count=1
    await perform_draw_with_fns_check(draw_type, 1)  # будет создан новый розыгрыш
    # В реальном коде нужно передавать original_draw_id, чтобы связать