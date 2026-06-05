import exifread
import io
from datetime import datetime
from sqlalchemy import select
from bot.config import START_DATE
from bot.models.database import AsyncSessionLocal, Receipt
from bot.services.easy_ocr import recognize_receipt
from bot.services.image_forensics import run_full_forensics

async def validate_receipt_photo(image_bytes: bytes):
    # 1. EXIF-проверка (Photoshop и др.)
    try:
        tags = exifread.process_file(io.BytesIO(image_bytes))
        software = tags.get('Image Software', None)
        if software and any(p in str(software) for p in ['Photoshop', 'GIMP', 'Adobe']):
            return False, "Фото отредактировано в графическом редакторе"
    except:
        pass

    # 2. Криминалистический анализ (ELA + DCT + шум)
    forensic = await run_full_forensics(image_bytes)
    if not forensic['forensic_passed']:
        fail_reasons = []
        for method, res in forensic['details'].items():
            if not res.get('passed', True):
                fail_reasons.append(f"{method}: {res.get('reason', 'Подозрение')}")
        reason = "; ".join(fail_reasons)
        return False, f"Чек не прошёл проверку подлинности: {reason}"

    # 3. OCR распознавание
    extracted = await recognize_receipt(image_bytes)
    if not extracted:
        return False, "Не удалось распознать чек"

    # 4. Проверка даты покупки
    start = datetime.strptime(START_DATE, "%Y-%m-%d")
    if extracted["purchase_date"] < start:
        return False, f"Чек ранее даты старта акции ({START_DATE})"
    if extracted["purchase_date"] > datetime.utcnow():
        return False, "Дата покупки в будущем"

    # 5. Уникальность чека
    async with AsyncSessionLocal() as session:
        existing = await session.execute(
            select(Receipt).where(
                Receipt.purchase_date == extracted["purchase_date"],
                Receipt.amount == extracted["amount"],
                Receipt.fp_code == extracted["fp_code"]
            )
        )
        if existing.scalar_one_or_none():
            return False, "Этот чек уже загружен"

    return True, "OK", extracted