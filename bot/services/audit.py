from datetime import datetime
from bot.models.database import AsyncSessionLocal, AuditLog

async def log_action(action: str, telegram_id: int = None, details: dict = None, ip: str = None):
    async with AsyncSessionLocal() as session:
        log_entry = AuditLog(
            action=action,
            telegram_id=telegram_id,
            details=details or {},
            ip_address=ip,
            created_at=datetime.utcnow()
        )
        session.add(log_entry)
        await session.commit()