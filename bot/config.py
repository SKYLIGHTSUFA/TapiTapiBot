import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = [int(id.strip()) for id in os.getenv("ADMIN_IDS", "").split(",") if id.strip()]
DATABASE_URL = os.getenv("DATABASE_URL")
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY")
MINIO_BUCKET = os.getenv("MINIO_BUCKET")
MINIO_SECURE = os.getenv("MINIO_SECURE", "False").lower() == "true"
ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY", "").encode()
ADMIN_WEB_PASSWORD = "secure_password"
TIMEZONE = os.getenv("TIMEZONE", "Europe/Moscow")
START_DATE = os.getenv("START_DATE", "2026-06-01")
MAIN_DRAW_DATE = os.getenv("MAIN_DRAW_DATE", "2026-12-21")
MAIN_DRAW_PRIZES = int(os.getenv("MAIN_DRAW_PRIZES", "3"))
END_DATE = os.getenv("END_DATE", "2026-12-28")
FNS_API_URL = os.getenv("FNS_API_URL")
FNS_API_KEY = os.getenv("FNS_API_KEY")
PROVERKACHEKA_API_URL = os.getenv("PROVERKACHEKA_API_URL", "https://proverkacheka.com/api/v1/check/get")
PROVERKACHEKA_TOKEN = "39928.KVmRrRbMpDNSOo6cy"
DEEPSEEK_OCR_MODEL = os.getenv("DEEPSEEK_OCR_MODEL", "deepseek-ai/DeepSeek-OCR-2")
DEEPSEEK_OCR_DEVICE = os.getenv("DEEPSEEK_OCR_DEVICE", "cuda")
DEEPSEEK_OCR_ENABLED = os.getenv("DEEPSEEK_OCR_ENABLED", "true").lower() == "true"
PUBLIC_IP = os.getenv("PUBLIC_IP", "72.56.20.106")
MEDIA_ROOT = os.getenv("MEDIA_ROOT", str(BASE_DIR / "media"))
STATIC_DIR = os.getenv("STATIC_DIR", str(BASE_DIR / "static"))
TEMPLATES_DIR = os.getenv("TEMPLATES_DIR", str(BASE_DIR / "templates"))
