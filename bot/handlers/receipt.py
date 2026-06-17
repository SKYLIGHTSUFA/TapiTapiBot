from aiogram import Router, F
from aiogram.types import Message
from datetime import datetime
import os
from bot.services.receipt_validator import validate_receipt_photo
from bot.services.ticket_manager import create_tickets_for_bottles
from bot.services.audit import log_action
from bot.models.database import AsyncSessionLocal, Receipt
from bot.config import MEDIA_ROOT

router = Router()

os.makedirs(MEDIA_ROOT, exist_ok=True)

@router.message(F.photo)
async def handle_receipt(message: Message):
    from bot.models.database import AsyncSessionLocal, User
    async with AsyncSessionLocal() as session:
        user = await session.get(User, message.from_user.id)
        if not user:
            await message.answer("Сначала зарегистрируйтесь: /start")
            return

    photo = message.photo[-1]
    file = await message.bot.get_file(photo.file_id)
    file_bytes = (await message.bot.download_file(file.file_path)).read()

    is_valid, error, extracted = await validate_receipt_photo(file_bytes)
    if not is_valid:
        await message.answer(f"❌ {error}", parse_mode=None)
        return

    filename = f"receipt_{message.from_user.id}_{int(datetime.utcnow().timestamp())}.jpg"
    filepath = os.path.join(MEDIA_ROOT, filename)
    with open(filepath, "wb") as f:
        f.write(file_bytes)

    async with AsyncSessionLocal() as session:
        receipt = Receipt(
            telegram_id=message.from_user.id,
            photo_url=f"/media/{filename}",
            purchase_date=extracted["purchase_date"],
            amount=extracted["amount"],
            fn_code=extracted["fn_code"],
            fp_code=extracted["fp_code"],
            receipt_number=extracted["receipt_number"],
            product_name=extracted["product_name"],
            raw_qr=extracted["raw_qr"],
            products_data=extracted["products_data"],
            bottles_count=extracted["bottles_count"],
            validated=True
        )
        session.add(receipt)
        await session.commit()
        receipt_id = receipt.id

    tickets = await create_tickets_for_bottles(message.from_user.id, receipt_id, extracted["products_data"])
    ticket_codes = "\n".join(f"`{ticket.code}`" for ticket in tickets[:10])
    more_text = f"\n...и ещё {len(tickets) - 10}" if len(tickets) > 10 else ""
    await message.answer(
        f"✅ Чек принят! Найдено бутылок Tapitapi: {len(tickets)}.\n"
        f"Создано билетов: {len(tickets)}\n\n"
        f"{ticket_codes}{more_text}\n\n"
        "Каждый билет участвует во всех розыгрышах, пока не выиграет или не будет аннулирован."
    )
    await log_action(
        "receipt_uploaded",
        message.from_user.id,
        {"receipt_id": receipt_id, "tickets": [ticket.code for ticket in tickets]},
    )
