from aiogram import Router, F
from aiogram.types import Message
from datetime import datetime
import io
from PIL import Image
from pillow_heif import register_heif_opener
from bot.services.receipt_validator import validate_receipt_photo
from bot.services.ticket_manager import create_ticket
from bot.services.audit import log_action
from bot.services.minio_client import upload_receipt_photo
from bot.models.database import AsyncSessionLocal, Receipt

register_heif_opener()
router = Router()

async def convert_heic_to_jpeg(file_bytes: bytes) -> bytes:
    """Конвертирует HEIC в JPEG"""
    image = Image.open(io.BytesIO(file_bytes))
    jpeg_io = io.BytesIO()
    image.convert("RGB").save(jpeg_io, format="JPEG", quality=90)
    return jpeg_io.getvalue()

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

    # Определяем тип (Telegram уже конвертирует HEIC в JPEG, но на всякий случай)
    # Если файл .heic – конвертируем
    if file.file_path.lower().endswith('.heic'):
        file_bytes = await convert_heic_to_jpeg(file_bytes)

    is_valid, error, extracted = await validate_receipt_photo(file_bytes)
    if not is_valid:
        await message.answer(f"❌ {error}")
        return

    filename = f"receipt_{message.from_user.id}_{int(dat.utcnow().timestamp())}.jpg"
    photo_url = await upload_receipt_photo(file_bytes, filename)

    async with AsyncSessionLocal() as session:
        receipt = Receipt(
            telegram_id=message.from_user.id,
            photo_url=photo_url,
            purchase_date=extracted["purchase_date"],
            amount=extracted["amount"],
            fp_code=extracted["fp_code"],
            receipt_number=extracted["receipt_number"],
            product_name=extracted["product_name"],
            validated=True
        )
        session.add(receipt)
        await session.commit()
        receipt_id = receipt.id

    ticket = await create_ticket(message.from_user.id, receipt_id)
    await message.answer(
        f"✅ Чек принят! Билет: `{ticket.code}`\n"
        "Участвует во всех розыгрышах. Удачи!"
    )
    await log_action("receipt_uploaded", message.from_user.id, {"ticket": ticket.code})