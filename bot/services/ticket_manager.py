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
    tickets = await create_tickets_for_bottles(telegram_id, receipt_id, [{"name": None, "ticket_count": 1}])
    return tickets[0]


async def create_tickets_for_bottles(telegram_id: int, receipt_id: int, products: list[dict]) -> list[Ticket]:
    tickets = []
    bottle_index = 1
    async with AsyncSessionLocal() as session:
        for product in products:
            for _ in range(int(product.get("ticket_count") or 0)):
                ticket = Ticket(
                    code=await generate_unique_ticket_code(),
                    telegram_id=telegram_id,
                    receipt_id=receipt_id,
                    product_name=product.get("name"),
                    bottle_index=bottle_index,
                    status=TicketStatus.ACTIVE,
                )
                session.add(ticket)
                tickets.append(ticket)
                bottle_index += 1
        await session.commit()
        for ticket in tickets:
            await session.refresh(ticket)
        return tickets