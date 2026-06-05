from minio import Minio
from minio.error import S3Error
import io
from bot.config import MINIO_ENDPOINT, MINIO_ACCESS_KEY, MINIO_SECRET_KEY, MINIO_BUCKET, MINIO_SECURE

_client = None

def get_minio_client():
    global _client
    if _client is None:
        _client = Minio(
            MINIO_ENDPOINT,
            access_key=MINIO_ACCESS_KEY,
            secret_key=MINIO_SECRET_KEY,
            secure=MINIO_SECURE
        )
        if not _client.bucket_exists(MINIO_BUCKET):
            _client.make_bucket(MINIO_BUCKET)
    return _client

async def upload_receipt_photo(image_bytes: bytes, filename: str) -> str:
    client = get_minio_client()
    try:
        client.put_object(
            MINIO_BUCKET,
            filename,
            io.BytesIO(image_bytes),
            length=len(image_bytes),
            content_type="image/jpeg"
        )
        return f"http://{MINIO_ENDPOINT}/{MINIO_BUCKET}/{filename}"
    except S3Error as e:
        raise Exception(f"MinIO upload failed: {e}")