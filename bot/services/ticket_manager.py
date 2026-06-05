import secrets
from sqlalchemy import select
from bot.models.database import AsyncSessionLocal, Ticket, TicketStatus

async def generate_unique_ticket_code() -> str:
    while True:
        code = ''.join(secrets.choice('0123456789') for _ in range(12))
        async with AsyncSessionLocal() as session:
            existing = await session.execute(select(Ticket).where(Ticket.code == code))
            if not existing.scalar_one_or_none():
                return code

async def create_ticket(telegram_id: int, receipt_id: int) -> Ticket:
    code = await generate_unique_ticket_code()
    async with AsyncSessionLocal() as session:
        ticket = Ticket(code=code, telegram_id=telegram_id, receipt_id=receipt_id, status=TicketStatus.ACTIVE)
        session.add(ticket)
        await session.commit()
        return ticket