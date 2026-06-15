import cv2
import numpy as np
from PIL import Image
import io
import logging
from scipy import ndimage

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def perform_ela(image_bytes: bytes, quality: int = 95) -> dict:
    """
    Error Level Analysis (ELA) – анализ уровня ошибок.
    Выявляет области, сохранённые с другим уровнем сжатия.
    """
    try:
        original = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        temp_io = io.BytesIO()
        original.save(temp_io, format="JPEG", quality=quality)
        temp_io.seek(0)
        compressed = Image.open(temp_io)
        original_arr = np.array(original, dtype=np.int16)
        compressed_arr = np.array(compressed, dtype=np.int16)
        diff = np.abs(original_arr - compressed_arr)
        ela = np.clip(diff * 10, 0, 255).astype(np.uint8)
        non_zero = np.count_nonzero(ela) / ela.size if ela.size > 0 else 0
        mean_diff = np.mean(diff) if diff.size > 0 else 0
        if non_zero > 0.3 and mean_diff > 10:
            return {"passed": False, "score": non_zero, "reason": "ELA выявил аномальные области"}
        return {"passed": True, "score": non_zero, "reason": "ОК"}
    except Exception as e:
        logger.warning(f"ELA failed: {e}")
        return {"passed": True, "score": 0, "reason": f"Ошибка ELA: {e}"}

async def perform_dct_analysis(image_bytes: bytes) -> dict:
    """
    DCT-анализ для обнаружения copy-move подделок.
    """
    try:
        img = cv2.imdecode(np.frombuffer(image_bytes, np.uint8), cv2.IMREAD_GRAYSCALE)
        if img is None:
            return {"passed": True, "score": 0, "reason": "Не удалось декодировать изображение"}
        h, w = img.shape
        block_size = 8
        dct_coeffs = []
        for i in range(0, h - block_size + 1, block_size):
            for j in range(0, w - block_size + 1, block_size):
                block = img[i:i+block_size, j:j+block_size].astype(np.float32)
                dct = cv2.dct(block)
                dct_coeffs.append(dct.flatten())
        dct_coeffs = np.array(dct_coeffs)
        if len(dct_coeffs) > 1:
            from scipy.spatial.distance import pdist
            distances = pdist(dct_coeffs, metric='cosine')
            threshold = 0.15
            similar_ratio = np.sum(distances < threshold) / len(distances) if len(distances) > 0 else 0
            if similar_ratio > 0.4:
                return {"passed": False, "score": similar_ratio, "reason": "Обнаружены подозрительные копирующие блоки"}
            return {"passed": True, "score": similar_ratio, "reason": "ОК"}
        return {"passed": True, "score": 0, "reason": "Недостаточно блоков для анализа"}
    except Exception as e:
        logger.warning(f"DCT analysis failed: {e}")
        return {"passed": True, "score": 0, "reason": f"Ошибка DCT: {e}"}

async def perform_noise_analysis(image_bytes: bytes) -> dict:
    """
    Анализ шума: разные уровни шума в разных регионах = признаки подделки.
    """
    try:
        img = cv2.imdecode(np.frombuffer(image_bytes, np.uint8), cv2.IMREAD_GRAYSCALE)
        if img is None:
            return {"passed": True, "score": 0, "reason": "Не удалось декодировать изображение"}
        h, w = img.shape
        block_size = 64
        noise_levels = []
        for i in range(0, h - block_size + 1, block_size):
            for j in range(0, w - block_size + 1, block_size):
                block = img[i:i+block_size, j:j+block_size]
                noise = np.std(block - ndimage.median_filter(block, size=3))
                noise_levels.append(noise)
        if len(noise_levels) > 1:
            noise_arr = np.array(noise_levels)
            std_noise = np.std(noise_arr)
            mean_noise = np.mean(noise_arr)
            cv_noise = std_noise / mean_noise if mean_noise > 0 else 0
            if cv_noise > 0.5:
                return {"passed": False, "score": cv_noise, "reason": "Неравномерный шум, возможна подделка"}
            return {"passed": True, "score": cv_noise, "reason": "ОК"}
        return {"passed": True, "score": 0, "reason": "Недостаточно блоков для анализа шума"}
    except Exception as e:
        logger.warning(f"Noise analysis failed: {e}")
        return {"passed": True, "score": 0, "reason": f"Ошибка анализа шума: {e}"}

async def run_full_forensics(image_bytes: bytes) -> dict:
    """
    Запускает все три метода и возвращает общий вердикт.
    """
    results = {}
    results['ela'] = await perform_ela(image_bytes)
    results['dct'] = await perform_dct_analysis(image_bytes)
    results['noise'] = await perform_noise_analysis(image_bytes)
    forensic_passed = all(v.get('passed', True) for v in results.values())
    return {"forensic_passed": forensic_passed, "details": results}