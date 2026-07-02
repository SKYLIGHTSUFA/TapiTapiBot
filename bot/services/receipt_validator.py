import exifread
import io
from datetime import datetime
from sqlalchemy import select
from bot.models.database import AsyncSessionLocal, Receipt
from bot.services.proverkacheka import ReceiptApiError, extract_qr_raw, fetch_receipt

async def validate_receipt_photo(image_bytes: bytes):
    # 1. EXIF-проверка
    try:
        tags = exifread.process_file(io.BytesIO(image_bytes))
        software = tags.get('Image Software', None)
        if software and any(p in str(software) for p in ['Photoshop', 'GIMP', 'Adobe']):
            return False, "Фото отредактировано в графическом редакторе", {}
    except:
        pass

    # 2. QR-код и проверка через API
    raw_qr = extract_qr_raw(image_bytes)
    try:
        extracted = await fetch_receipt(raw_qr=raw_qr, image_bytes=image_bytes)
    except ReceiptApiError as exc:
        if raw_qr:
            return False, str(exc), {}
        return False, "Не удалось проверить чек через API. Загрузите фото, где QR-код хорошо виден.", {}

    # 3. Проверка даты покупки
    if extracted["purchase_date"] > datetime.utcnow():
        return False, "Дата покупки в будущем", {}

    # 4. Уникальность чека
    async with AsyncSessionLocal() as session:
        existing = await session.execute(
            select(Receipt).where(
                Receipt.fn_code == extracted["fn_code"],
                Receipt.receipt_number == extracted["receipt_number"],
                Receipt.fp_code == extracted["fp_code"],
            )
        )
        if existing.scalar_one_or_none():
            return False, "Этот чек уже загружен", {}

    return True, "OK", extracted
