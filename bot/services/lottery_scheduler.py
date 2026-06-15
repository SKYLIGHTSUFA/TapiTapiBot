from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from datetime import datetime
import pytz
import secrets
import hashlib
import json
from sqlalchemy import select, func
from bot.config import TIMEZONE, DATABASE_URL, MAIN_DRAW_DATE, MAIN_DRAW_PRIZES, END_DATE
from bot.models.database import AsyncSessionLocal, Draw, DrawType, Ticket, TicketStatus, Receipt
from bot.services.audit import log_action

jobstores = {'default': SQLAlchemyJobStore(url=DATABASE_URL.replace("+asyncpg", ""))}
scheduler = AsyncIOScheduler(jobstores=jobstores, timezone=pytz.timezone(TIMEZONE))

def is_first_monday_of_month(dt: datetime) -> bool:
    return dt.weekday() == 0 and 1 <= dt.day <= 7

def is_main_draw_date(dt: datetime) -> bool:
    target = datetime.strptime(MAIN_DRAW_DATE, "%Y-%m-%d").replace(tzinfo=pytz.timezone(TIMEZONE))
    return dt.date() == target.date()

def is_after_end(dt: datetime) -> bool:
    end = datetime.strptime(END_DATE, "%Y-%m-%d").replace(tzinfo=pytz.timezone(TIMEZONE))
    return dt > end

def init_scheduler():
    scheduler.remove_all_jobs()
    tz = pytz.timezone(TIMEZONE)
    now = datetime.now(tz)
    if is_after_end(now):
        return
    main_draw_at = tz.localize(datetime.strptime(f"{MAIN_DRAW_DATE} 12:00", "%Y-%m-%d %H:%M"))
    # replace_existing=True чтобы при перезапуске не было конфликта
    scheduler.add_job(
        run_monday_draw,
        CronTrigger(day_of_week='mon', hour=12, minute=0, timezone=tz),
        id='monday_draw',
        replace_existing=True
    )
    scheduler.add_job(
        send_reminders,
        CronTrigger(day_of_week='mon', hour=9, minute=0, timezone=tz),
        id='reminder_job',
        replace_existing=True
    )
    if now < main_draw_at:
        scheduler.add_job(
            run_main_draw,
            DateTrigger(run_date=main_draw_at, timezone=tz),
            id='main_draw',
            replace_existing=True
        )
    scheduler.add_job(
        expire_pending_prizes,
        CronTrigger(minute=0, timezone=tz),
        id='expire_pending_prizes',
        replace_existing=True
    )
    scheduler.start()

async def run_monday_draw():
    now = datetime.now(pytz.timezone(TIMEZONE))
    if is_after_end(now):
        return
    await perform_draw_with_fns_check(DrawType.WEEKLY, 2)
    if is_first_monday_of_month(now):
        await perform_draw_with_fns_check(DrawType.MONTHLY, 5)

async def run_main_draw():
    now = datetime.now(pytz.timezone(TIMEZONE))
    if not is_after_end(now):
        await perform_draw_with_fns_check(DrawType.MAIN, MAIN_DRAW_PRIZES)

async def send_reminders():
    now = datetime.now(pytz.timezone(TIMEZONE))
    if is_main_draw_date(now) or is_after_end(now):
        return
    from bot.dispatcher import bot
    async with AsyncSessionLocal() as session:
        users = await session.execute(select(Ticket.telegram_id).where(Ticket.status == TicketStatus.ACTIVE).distinct())
        users = users.scalars().all()
    for uid in set(users):
        try:
            await bot.send_message(uid, "🔔 Напоминаем: сегодня в 12:00 розыгрыш! У вас есть активные билеты.")
        except:
            pass

async def perform_draw_with_fns_check(draw_type: DrawType, prizes_count: int):
    draw_time = datetime.utcnow()
    async with AsyncSessionLocal() as session:
        draw = Draw(draw_type=draw_type, scheduled_time=draw_time, status="pending")
        session.add(draw)
        await session.commit()
        draw_id = draw.id

    async with AsyncSessionLocal() as session:
        draw = await session.get(Draw, draw_id)
        tickets = (await session.execute(
            select(Ticket).where(
                Ticket.status == TicketStatus.ACTIVE,
                Ticket.created_at <= draw_time,
            )
        )).scalars().all()
        if not tickets:
            draw.status = "completed"
            draw.executed_at = datetime.utcnow()
            await session.commit()
            return

        temp_tickets = list(tickets)
        winners = []

        for prize_index in range(prizes_count):
            found = False
            while temp_tickets:
                idx = secrets.randbelow(len(temp_tickets))
                candidate = temp_tickets.pop(idx)
                receipt = await get_receipt_by_ticket(candidate.id)
                if not receipt or not receipt.validated:
                    await invalidate_ticket(candidate.id)
                    continue
                candidate.status = TicketStatus.WON
                candidate.won_in_draw = draw_type.value
                winners.append(candidate)
                found = True
                break
            if not found:
                break

        winners_data = [{"ticket_code": w.code, "telegram_id": w.telegram_id} for w in winners]
        draw.winners_data = winners_data
        draw.audit_hash = hashlib.sha256(json.dumps(winners_data).encode()).hexdigest()
        draw.status = "completed"
        draw.executed_at = datetime.utcnow()
        await session.commit()

    from bot.services.notification import send_prize_notification
    for w in winners:
        await send_prize_notification(w.telegram_id, w.code, draw_type, draw_id)

async def get_receipt_by_ticket(ticket_id: int):
    async with AsyncSessionLocal() as session:
        ticket = await session.get(Ticket, ticket_id)
        if ticket:
            return await session.get(Receipt, ticket.receipt_id)
        return None

async def invalidate_ticket(ticket_id: int):
    async with AsyncSessionLocal() as session:
        ticket = await session.get(Ticket, ticket_id)
        if ticket:
            ticket.status = TicketStatus.CANCELLED
            await session.commit()

async def expire_pending_prizes():
    from datetime import timedelta
    from bot.models.database import PrizeDelivery

    deadline = datetime.utcnow() - timedelta(hours=72)
    async with AsyncSessionLocal() as session:
        deliveries = (await session.execute(
            select(PrizeDelivery).where(
                PrizeDelivery.status == "pending",
                PrizeDelivery.notified_at <= deadline,
            )
        )).scalars().all()
        for delivery in deliveries:
            delivery.status = "expired"
            ticket = (await session.execute(
                select(Ticket).where(Ticket.code == delivery.ticket_code)
            )).scalar_one_or_none()
            if ticket:
                ticket.status = TicketStatus.CANCELLED
            await log_action(
                "winner_no_response",
                delivery.telegram_id,
                {"draw_id": delivery.draw_id, "ticket_code": delivery.ticket_code},
            )
        await session.commit()
