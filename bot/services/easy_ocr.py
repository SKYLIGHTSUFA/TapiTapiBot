import easyocr
import re
from datetime import datetime
from typing import Optional

reader = easyocr.Reader(['ru', 'en'], gpu=False)

async def recognize_receipt(image_bytes: bytes) -> Optional[dict]:
    result = reader.readtext(image_bytes, detail=0, paragraph=False)
    full_text = " ".join(result).upper()

    # Поиск названия продукта (разные варианты)
    product_found = any(
        re.search(pattern, full_text)
        for pattern in [r'ТАПИТАПИ', r'ТАПИТАЛИ', r'TAPITAPI']
    )
    if not product_found:
        return None

    # Дата
    date_match = re.search(r'\b(\d{2})\.(\d{2})\.(\d{2,4})\b', full_text)
    if not date_match:
        return None
    day, month, year = date_match.groups()
    if len(year) == 2:
        year = "20" + year
    try:
        purchase_date = datetime.strptime(f"{day}.{month}.{year}", "%d.%m.%Y")
    except ValueError:
        return None

    # Сумма
    amount_match = re.search(r'(?:ИТОГ|СУММА|ВСЕГО)[^\d]*(\d+[\.,]\d{2})', full_text)
    if not amount_match:
        amount_match = re.search(r'(\d+[\.,]\d{2})\s*(?:РУБ|RUB)', full_text)
    if not amount_match:
        return None
    amount = float(amount_match.group(1).replace(',', '.'))

    # Фискальный признак (ФП)
    fp_match = re.search(r'ФП[:\s]*(\d{10,})', full_text)
    fp_code = fp_match.group(1) if fp_match else ""

    # Номер чека
    num_match = re.search(r'(?:ЧЕК|НОМЕР ЧЕКА)[:\s#]*(\d+)', full_text)
    receipt_number = num_match.group(1) if num_match else ""

    return {
        "purchase_date": purchase_date,
        "amount": amount,
        "fp_code": fp_code,
        "receipt_number": receipt_number,
        "product_name": "Тапитапи"  # фиксированное название для базы
    }