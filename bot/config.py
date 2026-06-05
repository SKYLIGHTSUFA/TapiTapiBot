import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = [int(id.strip()) for id in os.getenv("ADMIN_IDS", "").split(",") if id.strip()]
DATABASE_URL = os.getenv("DATABASE_URL")
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY")
MINIO_BUCKET = os.getenv("MINIO_BUCKET")
MINIO_SECURE = os.getenv("MINIO_SECURE", "False").lower() == "true"
ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY", "").encode()
ADMIN_WEB_PASSWORD = os.getenv("ADMIN_WEB_PASSWORD")
TIMEZONE = os.getenv("TIMEZONE", "Europe/Moscow")
START_DATE = os.getenv("START_DATE", "2026-06-01")
MAIN_DRAW_DATE = os.getenv("MAIN_DRAW_DATE", "2026-12-21")
END_DATE = os.getenv("END_DATE", "2026-12-28")
FNS_API_URL = os.getenv("FNS_API_URL")
FNS_API_KEY = os.getenv("FNS_API_KEY")