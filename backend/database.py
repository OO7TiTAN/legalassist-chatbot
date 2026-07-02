from datetime import datetime
from typing import Optional
from sqlmodel import SQLModel, Field, Session, create_engine, select
from config import get_settings
import uuid
import os
import socket
from urllib.parse import quote

settings = get_settings()

# Build database engine
_db_host = os.environ.get("DB_HOST", "")
_db_pass = os.environ.get("DB_PASSWORD", "")
_db_user = os.environ.get("DB_USER", "postgres")
_db_port = os.environ.get("DB_PORT", "5432")

if _db_host and _db_pass:
    _encoded = quote(_db_pass, safe="")
    _db_url = f"postgresql+psycopg2://{_db_user}:{_encoded}@{_db_host}:{_db_port}/postgres?sslmode=require"

    # Force IPv4 — Render free tier can't reach Supabase via IPv6
    _ipv4 = None
    try:
        for info in socket.getaddrinfo(_db_host, 5432, socket.AF_INET):
            _ipv4 = info[4][0]
            break
    except Exception as e:
        print(f"[DB] IPv4 resolution warning: {e}")

    _connect_args = {"sslmode": "require"}
    if _ipv4:
        _connect_args["hostaddr"] = _ipv4
        print(f"[DB] Connecting to PostgreSQL at {_db_host} via IPv4 {_ipv4}")
    else:
        print(f"[DB] Connecting to PostgreSQL at {_db_host} (no IPv4 found, using default)")

    engine = create_engine(_db_url, echo=False, pool_pre_ping=True, pool_recycle=300,
                           connect_args=_connect_args)
else:
    _db_url = settings.database_url
    print(f"[DB] DATABASE_URL scheme: {_db_url.split('://')[0]}")
    if ("postgresql" in _db_url or "postgres" in _db_url) and "sslmode" not in _db_url:
        _db_url += "?sslmode=require"

    if "sqlite" in _db_url:
        engine = create_engine(_db_url, echo=False)
    else:
        engine = create_engine(_db_url, echo=False, pool_pre_ping=True, pool_recycle=300)




# ─── Models ───────────────────────────────────────────────────────────────────

class ChatSession(SQLModel, table=True):
    __tablename__ = "sessions"
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    page_url: Optional[str] = None
    referrer: Optional[str] = None
    started_at: datetime = Field(default_factory=datetime.utcnow)
    last_active: datetime = Field(default_factory=datetime.utcnow)
    message_count: int = Field(default=0)
    user_email: Optional[str] = None
    user_name: Optional[str] = None
    is_active: bool = Field(default=True)


class ChatMessage(SQLModel, table=True):
    __tablename__ = "messages"
    id: Optional[int] = Field(default=None, primary_key=True)
    session_id: str = Field(foreign_key="sessions.id", index=True)
    role: str  # 'user' or 'assistant'
    content: str
    suggested_url: Optional[str] = None
    suggested_title: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class CollectedUser(SQLModel, table=True):
    __tablename__ = "users"
    id: Optional[int] = Field(default=None, primary_key=True)
    session_id: str = Field(index=True)
    email: str = Field(index=True)
    name: Optional[str] = None
    query: Optional[str] = None
    page_url: Optional[str] = None
    collected_at: datetime = Field(default_factory=datetime.utcnow)
    email_sent: bool = Field(default=False)


class PageLink(SQLModel, table=True):
    __tablename__ = "page_links"
    id: Optional[int] = Field(default=None, primary_key=True)
    url: str = Field(unique=True, index=True)
    title: str
    category: Optional[str] = None
    last_updated: datetime = Field(default_factory=datetime.utcnow)


class AdminConfig(SQLModel, table=True):
    __tablename__ = "admin_config"
    id: Optional[int] = Field(default=None, primary_key=True)
    key: str = Field(unique=True, index=True)
    value: Optional[str] = None
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class TrafficEvent(SQLModel, table=True):
    __tablename__ = "traffic_events"
    id: Optional[int] = Field(default=None, primary_key=True)
    session_id: Optional[str] = None
    page_url: str
    referrer: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ContentChunk(SQLModel, table=True):
    __tablename__ = "content_chunks"
    id: Optional[int] = Field(default=None, primary_key=True)
    url: str = Field(index=True)
    title: str
    chunk_count: int = Field(default=0)
    last_scraped: datetime = Field(default_factory=datetime.utcnow)
    status: str = Field(default="indexed")  # indexed, error, skipped


# ─── Helpers ──────────────────────────────────────────────────────────────────

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session


def get_admin_config(key: str, default: str = None) -> Optional[str]:
    with Session(engine) as session:
        stmt = select(AdminConfig).where(AdminConfig.key == key)
        result = session.exec(stmt).first()
        return result.value if result else default


def set_admin_config(key: str, value: str):
    with Session(engine) as session:
        stmt = select(AdminConfig).where(AdminConfig.key == key)
        config = session.exec(stmt).first()
        if config:
            config.value = value
            config.updated_at = datetime.utcnow()
            session.add(config)
        else:
            session.add(AdminConfig(key=key, value=value))
        session.commit()


# ─── Default Config Seed ───────────────────────────────────────────────────────

DEFAULT_CONFIG = {
    "admin_email": "",
    "smtp_host": "smtp.gmail.com",
    "smtp_port": "587",
    "smtp_user": "",
    "smtp_password": "",
    "smtp_from_name": "LegalAssist Chatbot",
    "chatbot_name": "Legal Assist Bot",
    "chatbot_greeting": "Hello! I'm the Legal Assist Bot. How can I help you today? I can answer questions about our claims management services, legal advice, and more.",
    "auto_email_transcripts": "false",
    "email_notifications_enabled": "true",
}


def seed_default_config():
    with Session(engine) as session:
        for key, value in DEFAULT_CONFIG.items():
            stmt = select(AdminConfig).where(AdminConfig.key == key)
            existing = session.exec(stmt).first()
            if not existing:
                session.add(AdminConfig(key=key, value=value))
        session.commit()
