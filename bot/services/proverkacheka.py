import math
import re
from datetime import datetime
from difflib import SequenceMatcher
from urllib.parse import parse_qs, urlparse

import cv2
import httpx
import numpy as np

from bot.config import PROVERKACHEKA_API_URL, PROVERKACHEKA_TOKEN

TAPITAPI_NAMES = ("tapitapi", "тапитапи")
TAPITAPI_OCR_VARIANTS = ("tapitani", "тапитани")
TAPITAPI_SIMILARITY_THRESHOLD = 0.75


class ReceiptApiError(Exception):
    pass


def normalize_product_name(name: str) -> str:
    return " ".join((name or "").split())


def is_tapitapi_product(name: str) -> bool:
    normalized = normalize_product_name(name).casefold()
    aliases = TAPITAPI_NAMES + TAPITAPI_OCR_VARIANTS
    if any(alias in normalized for alias in aliases):
        return True

    words = re.findall(r"[a-zа-яё]+", normalized)
    for word in words:
        for alias in TAPITAPI_NAMES:
            if abs(len(word) - len(alias)) > 2:
                continue
            similarity = SequenceMatcher(None, word, alias).ratio()
            if similarity >= TAPITAPI_SIMILARITY_THRESHOLD:
                return True
    return False


def _decode_qr_with_opencv(image_bytes: bytes) -> str | None:
    image = cv2.imdecode(np.frombuffer(image_bytes, np.uint8), cv2.IMREAD_GRAYSCALE)
    if image is None:
        return None

    detector = cv2.QRCodeDetector()
    ok, decoded_info, _, _ = detector.detectAndDecodeMulti(image)
    if ok:
        for data in decoded_info:
            if data:
                return data

    data, _, _ = detector.detectAndDecode(image)
    return data or None


def _decode_qr_with_pyzbar(image_bytes: bytes) -> str | None:
    try:
        from pyzbar.pyzbar import decode
    except ImportError:
        return None

    image = cv2.imdecode(np.frombuffer(image_bytes, np.uint8), cv2.IMREAD_GRAYSCALE)
    if image is None:
        return None

    for qr in decode(image):
        data = qr.data.decode("utf-8", errors="ignore").strip()
        if data:
            return data
    return None


def extract_qr_raw(image_bytes: bytes) -> str | None:
    return _decode_qr_with_opencv(image_bytes) or _decode_qr_with_pyzbar(image_bytes)


def _parse_qr(raw_qr: str) -> dict:
    query = urlparse(raw_qr).query or raw_qr
    params = {key: values[0] for key, values in parse_qs(query, keep_blank_values=True).items()}
    return {
        "fn": params.get("fn", ""),
        "fd": params.get("i") or params.get("fd", ""),
        "fp": params.get("fp", ""),
        "date": params.get("t", ""),
        "sum": params.get("s", ""),
        "operation": params.get("n", ""),
    }


def _parse_datetime(value: str | int | None, raw_qr: str) -> datetime:
    if isinstance(value, int):
        return datetime.fromtimestamp(value)
    if value:
        for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%d.%m.%Y %H:%M:%S"):
            try:
                return datetime.strptime(str(value), fmt)
            except ValueError:
                pass

    qr_date = _parse_qr(raw_qr).get("date", "")
    for fmt in ("%Y%m%dT%H%M", "%Y%m%dT%H%M%S"):
        try:
            return datetime.strptime(qr_date, fmt)
        except ValueError:
            pass
    raise ReceiptApiError("Не удалось определить дату покупки")


def _kopecks_to_rubles(value: int | float | None) -> float:
    return round(float(value or 0) / 100, 2)


def _quantity_to_tickets(quantity: int | float | str | None) -> int:
    try:
        value = float(quantity or 0)
    except (TypeError, ValueError):
        value = 0
    return max(0, math.floor(value))


def _extract_tapitapi_items(receipt_json: dict) -> tuple[list[dict], int]:
    matched_items = []
    total_bottles = 0
    for item in receipt_json.get("items") or []:
        name = normalize_product_name(item.get("name", ""))
        if not is_tapitapi_product(name):
            continue
        quantity = item.get("quantity", 1)
        ticket_count = _quantity_to_tickets(quantity)
        if ticket_count == 0:
            continue
        matched_items.append(
            {
                "name": name,
                "quantity": quantity,
                "ticket_count": ticket_count,
                "price": _kopecks_to_rubles(item.get("price")),
                "sum": _kopecks_to_rubles(item.get("sum")),
            }
        )
        total_bottles += ticket_count
    return matched_items, total_bottles


async def fetch_receipt(raw_qr: str) -> dict:
    if not PROVERKACHEKA_TOKEN:
        raise ReceiptApiError("Не настроен PROVERKACHEKA_TOKEN для проверки чеков")

    async with httpx.AsyncClient(timeout=30) as client:
        try:
            response = await client.post(
                PROVERKACHEKA_API_URL,
                data={"token": PROVERKACHEKA_TOKEN, "qrraw": raw_qr},
            )
            response.raise_for_status()
            payload = response.json()
        except httpx.HTTPError as exc:
            raise ReceiptApiError("Сервис проверки чеков временно недоступен") from exc
        except ValueError as exc:
            raise ReceiptApiError("Сервис проверки чеков вернул некорректный ответ") from exc

    if payload.get("code") != 1:
        message = payload.get("message") or payload.get("data") or "Чек не найден в сервисе проверки"
        raise ReceiptApiError(str(message))

    receipt_json = (payload.get("data") or {}).get("json") or {}
    if not receipt_json:
        raise ReceiptApiError("В ответе сервиса нет данных чека")

    tapitapi_items, bottles_count = _extract_tapitapi_items(receipt_json)
    if bottles_count == 0:
        raise ReceiptApiError("API проверки чека не подтвердил наличие вина Tapitapi в номенклатуре")

    qr_params = _parse_qr(raw_qr)
    amount = _kopecks_to_rubles(receipt_json.get("totalSum"))
    return {
        "purchase_date": _parse_datetime(receipt_json.get("dateTime"), raw_qr),
        "amount": amount or float(qr_params.get("sum") or 0),
        "fn_code": str(receipt_json.get("fiscalDriveNumber") or qr_params["fn"]),
        "fp_code": str(receipt_json.get("fiscalSign") or qr_params["fp"]),
        "receipt_number": str(receipt_json.get("fiscalDocumentNumber") or qr_params["fd"]),
        "product_name": ", ".join(item["name"] for item in tapitapi_items),
        "products_data": tapitapi_items,
        "bottles_count": bottles_count,
        "raw_qr": raw_qr,
    }
