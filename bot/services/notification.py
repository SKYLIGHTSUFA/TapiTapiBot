from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from bot.dispatcher import bot
from bot.models.database import AsyncSessionLocal, PrizeDelivery, DrawType

async def send_prize_notification(telegram_id: int, ticket_code: str, draw_type: DrawType, draw_id: int):
    prize_type = "ozon" if draw_type in (DrawType.WEEKLY, DrawType.MONTHLY) else "main"
    prize_code = None
    if draw_type in (DrawType.WEEKLY, DrawType.MONTHLY):
        import secrets
        prize_code = f"OZON-{secrets.token_hex(8).upper()}"
        title = "🎉 Вы выиграли электронный сертификат Ozon на 2000₽!"
    else:
        title = "🏆 Вы выиграли главный приз!"

    async with AsyncSessionLocal() as session:
        delivery = PrizeDelivery(
            telegram_id=telegram_id,
            draw_id=draw_id,
            ticket_code=ticket_code,
            prize_type=prize_type,
            prize_code=prize_code,
            status="pending"
        )
        session.add(delivery)
        await session.commit()
        delivery_id = delivery.id

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Подтвердить получение", callback_data=f"confirm_prize:{delivery_id}")]
        ]
    )
    msg = (
        f"{title}\n"
        f"Выигравший билет: `{ticket_code}`\n\n"
        "Подтвердите получение приза в течение 72 часов. "
        "Если подтверждения не будет, выигравший билет будет аннулирован."
    )
    await bot.send_message(telegram_id, msg, reply_markup=keyboard)