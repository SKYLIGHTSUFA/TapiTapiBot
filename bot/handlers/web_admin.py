from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.responses import HTMLResponse
import secrets
from bot.config import ADMIN_WEB_PASSWORD
from bot.models.database import AsyncSessionLocal, User, Ticket, Draw, Receipt
from sqlalchemy import select, func

app = FastAPI(title="Тапитапи Админка")
security = HTTPBasic()

def verify_auth(credentials: HTTPBasicCredentials = Depends(security)):
    correct = secrets.compare_digest(credentials.password, ADMIN_WEB_PASSWORD)
    if not correct:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    return True

@app.get("/admin", response_class=HTMLResponse)
async def admin_panel(auth=Depends(verify_auth)):
    async with AsyncSessionLocal() as session:
        users_count = await session.scalar(select(func.count()).select_from(User))
        tickets_count = await session.scalar(select(func.count()).select_from(Ticket))
        active_tickets = await session.scalar(select(func.count()).select_from(Ticket).where(Ticket.status == "active"))
        draws_count = await session.scalar(select(func.count()).select_from(Draw))
        receipts_count = await session.scalar(select(func.count()).select_from(Receipt))
    return f"""
    <html>
    <head><title>Тапитапи Админка</title><style>body {{ font-family: Arial; margin: 40px; }}</style></head>
    <body>
    <h1>Панель администратора</h1>
    <ul>
        <li>👥 Пользователей: {users_count}</li>
        <li>🎫 Всего билетов: {tickets_count}</li>
        <li>✅ Активных билетов: {active_tickets}</li>
        <li>📄 Загружено чеков: {receipts_count}</li>
        <li>🎲 Проведено розыгрышей: {draws_count}</li>
    </ul>
    <hr>
    <p><a href="/admin/receipts">Просмотр чеков</a></p>
    </body>
    </html>
    """

@app.get("/admin/receipts", response_class=HTMLResponse)
async def list_receipts(auth=Depends(verify_auth)):
    async with AsyncSessionLocal() as session:
        receipts = await session.execute(select(Receipt).order_by(Receipt.uploaded_at.desc()).limit(50))
        receipts = receipts.scalars().all()
    rows = "".join(f"<tr><td>{r.id}</td><td>{r.telegram_id}</td><td>{r.purchase_date}</td><td>{r.amount}</td><td><a href='{r.photo_url}'>Фото</a></td></tr>" for r in receipts)
    return f"""
    <html><body>
    <h2>Последние чеки</h2>
    <table border="1"><tr><th>ID</th><th>User ID</th><th>Дата покупки</th><th>Сумма</th><th>Фото</th></tr>{rows}</table>
    </body></html>
    """

async def start_web_admin():
    import uvicorn
    config = uvicorn.Config(app, host="0.0.0.0", port=8000, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()