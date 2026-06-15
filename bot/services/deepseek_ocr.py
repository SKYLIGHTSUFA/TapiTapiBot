import asyncio
import io
import os
import re
import tempfile
from functools import lru_cache

from PIL import Image

from bot.config import DEEPSEEK_OCR_DEVICE, DEEPSEEK_OCR_ENABLED, DEEPSEEK_OCR_MODEL
from bot.services.proverkacheka import is_tapitapi_product, normalize_product_name


class DeepSeekOcrError(Exception):
    pass


@lru_cache(maxsize=1)
def _load_model():
    if not DEEPSEEK_OCR_ENABLED:
        raise DeepSeekOcrError("DeepSeek OCR отключен")

    try:
        import torch
        from transformers import AutoModel, AutoTokenizer
    except ImportError as exc:
        raise DeepSeekOcrError("Не установлены зависимости DeepSeek OCR") from exc

    if DEEPSEEK_OCR_DEVICE == "cuda" and not torch.cuda.is_available():
        raise DeepSeekOcrError("CUDA недоступна для DeepSeek OCR")

    tokenizer = AutoTokenizer.from_pretrained(DEEPSEEK_OCR_MODEL, trust_remote_code=True)
    model = AutoModel.from_pretrained(
        DEEPSEEK_OCR_MODEL,
        trust_remote_code=True,
        use_safetensors=True,
        torch_dtype=torch.bfloat16 if DEEPSEEK_OCR_DEVICE == "cuda" else torch.float32,
    )
    model = model.eval()
    if DEEPSEEK_OCR_DEVICE == "cuda":
        model = model.cuda()
    return tokenizer, model


def _save_temp_image(image_bytes: bytes) -> str:
    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    fd, image_path = tempfile.mkstemp(suffix=".jpg")
    os.close(fd)
    image.save(image_path, format="JPEG", quality=95)
    return image_path


def _run_ocr_sync(image_bytes: bytes) -> str:
    tokenizer, model = _load_model()
    image_path = _save_temp_image(image_bytes)
    output_dir = tempfile.mkdtemp(prefix="deepseek_ocr_")
    try:
        prompt = "<image>\nFree OCR."
        result = model.infer(
            tokenizer,
            prompt=prompt,
            image_file=image_path,
            output_path=output_dir,
            base_size=1024,
            image_size=768,
            crop_mode=True,
            save_results=False,
        )
        return str(result or "")
    finally:
        try:
            os.remove(image_path)
        except OSError:
            pass


async def recognize_receipt_text(image_bytes: bytes) -> str:
    return await asyncio.to_thread(_run_ocr_sync, image_bytes)


def _extract_quantity(line: str) -> int:
    quantity_patterns = [
        r"(?:кол-?во|количество|qty|x)\s*[:=]?\s*(\d+(?:[,.]\d+)?)",
        r"(\d+(?:[,.]\d+)?)\s*(?:шт|бут|бутыл)",
        r"\bx\s*(\d+(?:[,.]\d+)?)\b",
    ]
    for pattern in quantity_patterns:
        match = re.search(pattern, line, flags=re.IGNORECASE)
        if match:
            return max(1, int(float(match.group(1).replace(",", "."))))
    return 1


async def extract_tapitapi_items(image_bytes: bytes) -> list[dict]:
    text = await recognize_receipt_text(image_bytes)
    items = []
    for raw_line in text.splitlines():
        line = normalize_product_name(raw_line)
        if not is_tapitapi_product(line):
            continue
        ticket_count = _extract_quantity(line)
        items.append(
            {
                "name": line[:255],
                "quantity": ticket_count,
                "ticket_count": ticket_count,
                "price": 0,
                "sum": 0,
                "source": "deepseek_ocr",
            }
        )
    return items
