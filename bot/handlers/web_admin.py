from bot.services.audit import log_action
from fastapi.staticfiles import StaticFiles
from fastapi import FastAPI, HTTPException, Depends, status, Request, Form
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.responses import HTMLResponse, FileResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
import secrets
import os
import csv
import io
from datetime import datetime, timedelta
from sqlalchemy import select, func
from bot.config import ADMIN_WEB_PASSWORD, MEDIA_ROOT, STATIC_DIR, TEMPLATES_DIR
from bot.models.database import AsyncSessionLocal, User, Ticket, Draw, Receipt, TicketStatus, AuditLog

app = FastAPI(title="Тапитапи Админка")
os.makedirs(MEDIA_ROOT, exist_ok=True)
os.makedirs(STATIC_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
security = HTTPBasic()
templates = Jinja2Templates(directory=TEMPLATES_DIR)

def verify_auth(credentials: HTTPBasicCredentials = Depends(security)):
    correct = secrets.compare_digest(credentials.password, ADMIN_WEB_PASSWORD)
    if not correct:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    return True

@app.get("/admin", response_class=HTMLResponse)
async def admin_panel(request: Request, auth=Depends(verify_auth)):
    async with AsyncSessionLocal() as session:
        users_count = await session.scalar(select(func.count()).select_from(User))
        tickets_count = await session.scalar(select(func.count()).select_from(Ticket))
        active_tickets = await session.scalar(select(func.count()).select_from(Ticket).where(Ticket.status == TicketStatus.ACTIVE))
        receipts_count = await session.scalar(select(func.count()).select_from(Receipt))
        draws_count = await session.scalar(select(func.count()).select_from(Draw))
        today = datetime.utcnow().date()
        users_by_day, tickets_by_day, labels = [], [], []
        for i in range(6, -1, -1):
            day = today - timedelta(days=i)
            labels.append(day.strftime("%d.%m"))
            next_day = day + timedelta(days=1)
            cnt_users = await session.scalar(select(func.count()).select_from(User).where(User.registered_at >= day, User.registered_at < next_day))
            cnt_tickets = await session.scalar(select(func.count()).select_from(Ticket).where(Ticket.created_at >= day, Ticket.created_at < next_day))
            users_by_day.append(cnt_users or 0)
            tickets_by_day.append(cnt_tickets or 0)
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "users_count": users_count,
        "tickets_count": tickets_count,
        "active_tickets": active_tickets,
        "receipts_count": receipts_count,
        "draws_count": draws_count,
        "users_chart_data": {"labels": labels, "values": users_by_day},
        "tickets_chart_data": {"labels": labels, "values": tickets_by_day}
    })

@app.get("/admin/receipts", response_class=HTMLResponse)
async def list_receipts(request: Request, auth=Depends(verify_auth), search: str = None, page: int = 1):
    limit = 20
    offset = (page - 1) * limit
    async with AsyncSessionLocal() as session:
        query = select(Receipt).order_by(Receipt.uploaded_at.desc())
        if search:
            if search.isdigit():
                query = query.where(Receipt.telegram_id == int(search))
            else:
                query = query.where(Receipt.product_name.contains(search))
        receipts = await session.execute(query.offset(offset).limit(limit))
        receipts = receipts.scalars().all()
        total = await session.scalar(select(func.count()).select_from(Receipt))
        pages = (total + limit - 1) // limit
    return templates.TemplateResponse("receipts.html", {"request": request, "receipts": receipts, "page": page, "pages": pages, "search": search})

@app.get("/admin/tickets", response_class=HTMLResponse)
async def list_tickets(request: Request, auth=Depends(verify_auth), search: str = None, page: int = 1):
    limit = 50
    offset = (page - 1) * limit
    async with AsyncSessionLocal() as session:
        query = select(Ticket).order_by(Ticket.created_at.desc())
        if search:
            if search.isdigit():
                query = query.where(Ticket.telegram_id == int(search))
            else:
                query = query.where(Ticket.code.contains(search))
        tickets = await session.execute(query.offset(offset).limit(limit))
        tickets = tickets.scalars().all()
        total = await session.scalar(select(func.count()).select_from(Ticket))
        pages = (total + limit - 1) // limit
    return templates.TemplateResponse("tickets.html", {"request": request, "tickets": tickets, "page": page, "pages": pages, "search": search})

@app.get("/admin/users", response_class=HTMLResponse)
async def list_users(request: Request, auth=Depends(verify_auth), page: int = 1):
    limit = 50
    offset = (page - 1) * limit
    async with AsyncSessionLocal() as session:
        users = await session.execute(select(User).order_by(User.registered_at.desc()).offset(offset).limit(limit))
        users = users.scalars().all()
        total = await session.scalar(select(func.count()).select_from(User))
        pages = (total + limit - 1) // limit
    return templates.TemplateResponse("users.html", {"request": request, "users": users, "page": page, "pages": pages})

@app.get("/admin/draws", response_class=HTMLResponse)
async def list_draws(request: Request, auth=Depends(verify_auth)):
    async with AsyncSessionLocal() as session:
        draws = await session.execute(select(Draw).order_by(Draw.scheduled_time.desc()))
        draws = draws.scalars().all()
    return templates.TemplateResponse("draws.html", {"request": request, "draws": draws})

@app.get("/admin/export", response_class=HTMLResponse)
async def export_page(request: Request, auth=Depends(verify_auth)):
    return templates.TemplateResponse("export.html", {"request": request})

@app.post("/admin/export/csv")
async def export_csv(data_type: str = Form(...), auth=Depends(verify_auth)):
    async with AsyncSessionLocal() as session:
        output = io.StringIO()
        writer = csv.writer(output, delimiter=';')
        if data_type == "users":
            users = await session.execute(select(User))
            users = users.scalars().all()
            writer.writerow(["telegram_id", "full_name", "phone", "birth_date", "registered_at"])
            for u in users:
                writer.writerow([u.telegram_id, u.full_name, u.phone, u.birth_date, u.registered_at])
        elif data_type == "tickets":
            tickets = await session.execute(select(Ticket))
            tickets = tickets.scalars().all()
            writer.writerow(["code", "telegram_id", "status", "created_at", "won_in_draw"])
            for t in tickets:
                writer.writerow([t.code, t.telegram_id, t.status.value, t.created_at, t.won_in_draw])
        elif data_type == "receipts":
            receipts = await session.execute(select(Receipt))
            receipts = receipts.scalars().all()
            writer.writerow(["id", "telegram_id", "purchase_date", "amount", "product_name", "uploaded_at"])
            for r in receipts:
                writer.writerow([r.id, r.telegram_id, r.purchase_date, r.amount, r.product_name, r.uploaded_at])
    response = StreamingResponse(iter([output.getvalue()]), media_type="text/csv")
    response.headers["Content-Disposition"] = f"attachment; filename={data_type}_{datetime.utcnow().strftime('%Y%m%d')}.csv"
    return response

@app.get("/admin/logs", response_class=HTMLResponse)
async def view_logs(request: Request, auth=Depends(verify_auth), page: int = 1, start_date: str = None, end_date: str = None):
    limit = 50
    offset = (page - 1) * limit
    async with AsyncSessionLocal() as session:
        query = select(AuditLog).order_by(AuditLog.created_at.desc())
        if start_date:
            start = datetime.strptime(start_date, "%Y-%m-%d")
            query = query.where(AuditLog.created_at >= start)
        if end_date:
            end = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
            query = query.where(AuditLog.created_at < end)
        total = await session.scalar(select(func.count()).select_from(AuditLog))
        logs = await session.execute(query.offset(offset).limit(limit))
        logs = logs.scalars().all()
        pages = (total + limit - 1) // limit
    return templates.TemplateResponse("logs.html", {
        "request": request,
        "logs": logs,
        "page": page,
        "pages": pages,
        "start_date": start_date,
        "end_date": end_date
    })

@app.post("/admin/export/logs")
async def export_logs(start_date: str = Form(None), end_date: str = Form(None), auth=Depends(verify_auth)):
    async with AsyncSessionLocal() as session:
        query = select(AuditLog).order_by(AuditLog.created_at)
        if start_date:
            start = datetime.strptime(start_date, "%Y-%m-%d")
            query = query.where(AuditLog.created_at >= start)
        if end_date:
            end = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
            query = query.where(AuditLog.created_at < end)
        logs = await session.execute(query)
        logs = logs.scalars().all()
    output = io.StringIO()
    writer = csv.writer(output, delimiter=';')
    writer.writerow(["id", "action", "telegram_id", "details", "ip_address", "created_at"])
    for log in logs:
        writer.writerow([log.id, log.action, log.telegram_id, str(log.details), log.ip_address, log.created_at])
    response = StreamingResponse(iter([output.getvalue()]), media_type="text/csv")
    filename = f"logs_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
    response.headers["Content-Disposition"] = f"attachment; filename={filename}"
    return response

@app.get("/media/{filename}")
async def get_media(filename: str):
    file_path = os.path.join(MEDIA_ROOT, filename)
    if os.path.exists(file_path):
        return FileResponse(file_path)
    return {"error": "File not found"}

async def start_web_admin():
    import uvicorn
    config = uvicorn.Config(app, host="0.0.0.0", port=8000, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()

@app.post("/admin/export/logs")
async def export_logs(start_date: str = Form(None), end_date: str = Form(None), auth=Depends(verify_auth)):
    async with AsyncSessionLocal() as session:
        query = select(AuditLog).order_by(AuditLog.created_at)
        if start_date:
            start = datetime.strptime(start_date, "%Y-%m-%d")
            query = query.where(AuditLog.created_at >= start)
        if end_date:
            end = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
            query = query.where(AuditLog.created_at < end)
        logs = await session.execute(query)
        logs = logs.scalars().all()
    output = io.StringIO()
    writer = csv.writer(output, delimiter=';')
    writer.writerow(["id", "action", "telegram_id", "details", "ip_address", "created_at"])
    for log in logs:
        writer.writerow([log.id, log.action, log.telegram_id, str(log.details), log.ip_address, log.created_at])
    response = StreamingResponse(iter([output.getvalue()]), media_type="text/csv")
    filename = f"logs_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
    response.headers["Content-Disposition"] = f"attachment; filename={filename}"
    return response

@app.post("/admin/user/delete")
async def delete_user(telegram_id: int = Form(...), auth=Depends(verify_auth)):
    async with AsyncSessionLocal() as session:
        user = await session.get(User, telegram_id)
        if user:
            await session.delete(user)
            await session.commit()
            return {"status": "ok"}
    return {"status": "error"}

@app.post("/admin/ticket/cancel")
async def cancel_ticket(ticket_id: int = Form(...), auth=Depends(verify_auth)):
    async with AsyncSessionLocal() as session:
        ticket = await session.get(Ticket, ticket_id)
        if ticket:
            ticket.status = TicketStatus.CANCELLED
            await session.commit()
            await log_action("ticket_cancelled_admin", None, {"ticket_id": ticket_id})
            return {"status": "ok"}
    return {"status": "error"}
