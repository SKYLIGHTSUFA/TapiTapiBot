import io
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
TAPITAPI_ALIASES = ("tapitani", "тапитани")
TAPITAPI_SIMILARITY_THRESHOLD = 0.75


class ReceiptApiError(Exception):
    pass


def normalize_product_name(name: str) -> str:
    return " ".join((name or "").split())


def is_tapitapi_product(name: str) -> bool:
    normalized = normalize_product_name(name).casefold()
    aliases = TAPITAPI_NAMES + TAPITAPI_ALIASES
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


def _normalize_datetime_string(value: str) -> str:
    return (value or "").strip().replace("t", "T")


def _parse_datetime(value: str | int | None, raw_qr: str) -> datetime:
    if isinstance(value, int):
        return datetime.fromtimestamp(value)

    candidates = []
    if value:
        candidates.append(_normalize_datetime_string(str(value)))
    qr_date = _normalize_datetime_string(_parse_qr(raw_qr).get("date", ""))
    if qr_date:
        candidates.append(qr_date)

    formats = (
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%d.%m.%Y %H:%M:%S",
        "%Y%m%dT%H%M",
        "%Y%m%dT%H%M%S",
    )
    for candidate in candidates:
        for fmt in formats:
            try:
                return datetime.strptime(candidate, fmt)
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
    if value >= 1000:
        return max(0, math.floor(value / 1000))
    return max(0, math.floor(value))


def _extract_tapitapi_items(receipt_json: dict) -> tuple[list[dict], int]:
    matched_items = []
    total_bottles = 0
    for item in receipt_json.get("items") or []:
        name = normalize_product_name(item.get("name", ""))
        if not is_tapitapi_product(name):
            continue
        quantity = item.get("quantity", 1000)
        ticket_count = _quantity_to_tickets(quantity)
        if ticket_count == 0:
            continue
        matched_items.append(
            {
                "name": name,
                "quantity": ticket_count,
                "ticket_count": ticket_count,
                "price": _kopecks_to_rubles(item.get("price")),
                "sum": _kopecks_to_rubles(item.get("sum")),
            }
        )
        total_bottles += ticket_count
    return matched_items, total_bottles


def _parse_api_payload(payload: dict, fallback_qr: str | None) -> dict:
    if payload.get("code") != 1:
        message = payload.get("message") or payload.get("data") or "Чек не найден в сервисе проверки"
        raise ReceiptApiError(str(message))

    data = payload.get("data") or {}
    receipt_json = data.get("json") or {}
    if not receipt_json:
        raise ReceiptApiError("В ответе сервиса нет данных чека")

    tapitapi_items, bottles_count = _extract_tapitapi_items(receipt_json)
    if bottles_count == 0:
        raise ReceiptApiError("API проверки чека не подтвердил наличие вина Tapitapi в номенклатуре")

    request_data = payload.get("request") or {}
    manual = request_data.get("manual") or {}
    raw_qr = request_data.get("qrraw") or fallback_qr or ""
    qr_params = _parse_qr(raw_qr) if raw_qr else {}

    amount = _kopecks_to_rubles(receipt_json.get("totalSum"))
    if not amount and manual.get("sum"):
        amount = float(manual["sum"])
    if not amount and qr_params.get("sum"):
        amount = float(qr_params["sum"])

    return {
        "purchase_date": _parse_datetime(receipt_json.get("dateTime"), raw_qr),
        "amount": amount,
        "fn_code": str(receipt_json.get("fiscalDriveNumber") or manual.get("fn") or qr_params.get("fn", "")),
        "fp_code": str(receipt_json.get("fiscalSign") or manual.get("fp") or qr_params.get("fp", "")),
        "receipt_number": str(
            receipt_json.get("fiscalDocumentNumber") or manual.get("fd") or qr_params.get("fd", "")
        ),
        "product_name": ", ".join(item["name"] for item in tapitapi_items),
        "products_data": tapitapi_items,
        "bottles_count": bottles_count,
        "raw_qr": raw_qr,
    }


async def _request_receipt(client: httpx.AsyncClient, raw_qr: str | None, image_bytes: bytes | None) -> dict:
    if raw_qr:
        response = await client.post(
            PROVERKACHEKA_API_URL,
            data={"token": PROVERKACHEKA_TOKEN, "qrraw": raw_qr},
        )
        return response

    if image_bytes:
        files = {"qrfile": ("receipt.jpg", io.BytesIO(image_bytes), "image/jpeg")}
        response = await client.post(
            PROVERKACHEKA_API_URL,
            data={"token": PROVERKACHEKA_TOKEN},
            files=files,
        )
        return response

    raise ReceiptApiError("Нет данных для проверки чека")


async def _post_receipt(client: httpx.AsyncClient, raw_qr: str | None, image_bytes: bytes | None) -> dict:
    response = await _request_receipt(client, raw_qr, image_bytes)
    response.raise_for_status()
    return response.json()


async def fetch_receipt(raw_qr: str | None = None, image_bytes: bytes | None = None) -> dict:
    if not PROVERKACHEKA_TOKEN:
        raise ReceiptApiError("Не настроен PROVERKACHEKA_TOKEN для проверки чеков")
    if not raw_qr and not image_bytes:
        raise ReceiptApiError("Нет данных для проверки чека")

    async with httpx.AsyncClient(timeout=60) as client:
        try:
            if raw_qr:
                payload = await _post_receipt(client, raw_qr, None)
                if payload.get("code") != 1 and image_bytes:
                    payload = await _post_receipt(client, None, image_bytes)
            else:
                payload = await _post_receipt(client, None, image_bytes)
        except httpx.HTTPError as exc:
            raise ReceiptApiError("Сервис проверки чеков временно недоступен") from exc
        except ValueError as exc:
            raise ReceiptApiError("Сервис проверки чеков вернул некорректный ответ") from exc

        return _parse_api_payload(payload, raw_qr)
