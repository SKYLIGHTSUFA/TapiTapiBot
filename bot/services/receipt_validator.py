import exifread
import io
from datetime import datetime
from sqlalchemy import select
from bot.models.database import AsyncSessionLocal, Receipt
from bot.services.deepseek_ocr import (
    DeepSeekOcrError,
    extract_tapitapi_items_from_text,
    format_ocr_preview,
    recognize_receipt_text,
)
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

    # 2. Сначала отсекаем чеки без Tapitapi через OCR, чтобы не тратить лимит API.
    try:
        ocr_text = await recognize_receipt_text(image_bytes)
        ocr_items = extract_tapitapi_items_from_text(ocr_text)
    except DeepSeekOcrError as exc:
        return False, f"Не удалось выполнить OCR-проверку чека: {exc}", {}
    except Exception as exc:
        return False, f"Не удалось выполнить OCR-проверку чека: {exc}", {}

    if not ocr_items:
        return False, (
            "В чеке не найдено вино Tapitapi, участвующее в розыгрыше.\n\n"
            "OCR увидел:\n"
            f"{format_ocr_preview(ocr_text)}"
        ), {}

    # 3. Получение фискальных данных через API проверки чеков
    raw_qr = extract_qr_raw(image_bytes)
    if not raw_qr:
        return False, "Не удалось считать QR-код чека. Загрузите фото, где QR-код хорошо виден.", {}

    try:
        extracted = await fetch_receipt(raw_qr)
    except ReceiptApiError as exc:
        return False, str(exc), {}

    # 4. Проверка даты покупки
    if extracted["purchase_date"] > datetime.utcnow():
        return False, "Дата покупки в будущем", {}

    # 5. Уникальность чека
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
