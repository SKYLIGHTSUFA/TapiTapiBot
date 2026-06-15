from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base, Mapped, mapped_column
from sqlalchemy import String, DateTime, Integer, Boolean, Text, BigInteger, Enum, JSON, create_engine, inspect, text
from datetime import datetime
import enum
from bot.config import DATABASE_URL

# Асинхронный движок для работы бота
async_engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(async_engine, expire_on_commit=False)

# Синхронный движок для создания таблиц
sync_database_url = DATABASE_URL.replace("+asyncpg", "")
sync_engine = create_engine(sync_database_url, echo=False)

Base = declarative_base()

class UserStatus(enum.Enum):
    ACTIVE = "active"
    BLOCKED = "blocked"

class TicketStatus(enum.Enum):
    ACTIVE = "active"
    WON = "won"
    CANCELLED = "cancelled"

class DrawType(enum.Enum):
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    HALF_YEAR = "half_year"
    MAIN = "main"

class User(Base):
    __tablename__ = "users"
    telegram_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    full_name: Mapped[str] = mapped_column(String(255))
    phone: Mapped[str] = mapped_column(String(20))
    birth_date: Mapped[str] = mapped_column(String(10))
    city: Mapped[str] = mapped_column(String(100))
    status: Mapped[UserStatus] = mapped_column(Enum(UserStatus), default=UserStatus.ACTIVE)
    registered_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class Receipt(Base):
    __tablename__ = "receipts"
    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger)
    photo_url: Mapped[str] = mapped_column(String(500))
    purchase_date: Mapped[datetime] = mapped_column(DateTime)
    amount: Mapped[float] = mapped_column()
    fn_code: Mapped[str] = mapped_column(String(50), nullable=True)
    fp_code: Mapped[str] = mapped_column(String(50))
    receipt_number: Mapped[str] = mapped_column(String(50))
    product_name: Mapped[str] = mapped_column(String(255))
    raw_qr: Mapped[str] = mapped_column(Text, nullable=True)
    products_data: Mapped[list] = mapped_column(JSON, nullable=True)
    bottles_count: Mapped[int] = mapped_column(Integer, default=0)
    validated: Mapped[bool] = mapped_column(default=False)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class Ticket(Base):
    __tablename__ = "tickets"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger)
    receipt_id: Mapped[int] = mapped_column()
    product_name: Mapped[str] = mapped_column(String(255), nullable=True)
    bottle_index: Mapped[int] = mapped_column(Integer, nullable=True)
    status: Mapped[TicketStatus] = mapped_column(Enum(TicketStatus), default=TicketStatus.ACTIVE)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    won_in_draw: Mapped[str] = mapped_column(String(50), nullable=True)

class Draw(Base):
    __tablename__ = "draws"
    id: Mapped[int] = mapped_column(primary_key=True)
    draw_type: Mapped[DrawType] = mapped_column(Enum(DrawType))
    scheduled_time: Mapped[datetime] = mapped_column(DateTime)
    executed_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    winners_data: Mapped[dict] = mapped_column(JSON, nullable=True)
    audit_hash: Mapped[str] = mapped_column(String(128), nullable=True)

class PrizeDelivery(Base):
    __tablename__ = "prize_delivery"
    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger)
    draw_id: Mapped[int] = mapped_column()
    ticket_code: Mapped[str] = mapped_column(String(20))
    prize_type: Mapped[str] = mapped_column(String(50))
    prize_code: Mapped[str] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    notified_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    responded_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    retry_count: Mapped[int] = mapped_column(default=0)

class AuditLog(Base):
    __tablename__ = "audit_log"
    id: Mapped[int] = mapped_column(primary_key=True)
    action: Mapped[str] = mapped_column(String(100))
    telegram_id: Mapped[int] = mapped_column(BigInteger, nullable=True)
    details: Mapped[dict] = mapped_column(JSON)
    ip_address: Mapped[str] = mapped_column(String(45), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

async def init_db():
    # Используем синхронный движок для создания таблиц
    Base.metadata.create_all(bind=sync_engine)
    ensure_schema()

def ensure_schema():
    inspector = inspect(sync_engine)
    existing_tables = set(inspector.get_table_names())
    if "receipts" in existing_tables:
        existing_columns = {column["name"] for column in inspector.get_columns("receipts")}
        add_columns = {
            "fn_code": "VARCHAR(50)",
            "raw_qr": "TEXT",
            "products_data": "JSON",
            "bottles_count": "INTEGER DEFAULT 0",
        }
        with sync_engine.begin() as conn:
            for column_name, column_type in add_columns.items():
                if column_name not in existing_columns:
                    conn.execute(text(f"ALTER TABLE receipts ADD COLUMN {column_name} {column_type}"))
    if "tickets" in existing_tables:
        existing_columns = {column["name"] for column in inspector.get_columns("tickets")}
        add_columns = {
            "product_name": "VARCHAR(255)",
            "bottle_index": "INTEGER",
        }
        with sync_engine.begin() as conn:
            for column_name, column_type in add_columns.items():
                if column_name not in existing_columns:
                    conn.execute(text(f"ALTER TABLE tickets ADD COLUMN {column_name} {column_type}"))
