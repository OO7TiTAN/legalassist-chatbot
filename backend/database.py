from datetime import datetime
from typing import Optional
from sqlmodel import SQLModel, Field, Session, create_engine, select
from config import get_settings
import uuid
import os
from urllib.parse import quote

settings = get_settings()

# ── Database engine ────────────────────────────────────────────────────────────
# Priority: OS env vars → pydantic Settings fields → sqlite fallback
# For Neon (production), DB_HOST / DB_USER / DB_PASSWORD / DB_PORT / DB_NAME
# are set on Render. For local dev, set them in .env or use the sqlite fallback.

_db_host = os.environ.get("DB_HOST", "") or settings.db_host
_db_pass = os.environ.get("DB_PASSWORD", "") or settings.db_password
_db_user = os.environ.get("DB_USER", "") or settings.db_user
_db_port = os.environ.get("DB_PORT", "") or settings.db_port
_db_name = os.environ.get("DB_NAME", "") or settings.db_name

if _db_host and _db_pass:
    _encoded = quote(_db_pass, safe="")
    # sslmode passed via connect_args only — avoids psycopg2 duplicate-param error
    _db_url = f"postgresql+psycopg2://{_db_user}:{_encoded}@{_db_host}:{_db_port}/{_db_name}"

    _connect_args = {"sslmode": "require"}
    print(f"[DB] Connecting to Neon/{_db_name} at {_db_host}:{_db_port}")

    engine = create_engine(
        _db_url,
        echo=False,
        pool_pre_ping=True,
        pool_recycle=300,
        connect_args=_connect_args,
    )
else:
    # Local dev fallback — SQLite
    _db_url = settings.database_url
    print(f"[DB] Using local SQLite: {_db_url}")
    engine = create_engine(_db_url, echo=False)





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
