from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from sqlmodel import Session, select
from database import (
    ChatSession, ChatMessage, CollectedUser, ContentChunk,
    get_session, get_admin_config, set_admin_config
)
from auth import create_access_token, get_current_admin
from config import get_settings
from scraper import scrape_and_index
from embeddings import index_chunks, get_collection_count

router = APIRouter(prefix="/admin", tags=["admin"])
settings = get_settings()

# In-memory scrape status tracker
_scrape_status: dict = {"running": False, "last_run": None, "last_result": None}


class LoginRequest(BaseModel):
    password: str


class SettingsUpdate(BaseModel):
    admin_email: Optional[str] = None
    smtp_host: Optional[str] = None
    smtp_port: Optional[str] = None
    smtp_user: Optional[str] = None
    smtp_password: Optional[str] = None
    smtp_from_name: Optional[str] = None
    chatbot_name: Optional[str] = None
    chatbot_greeting: Optional[str] = None
    auto_email_transcripts: Optional[str] = None
    email_notifications_enabled: Optional[str] = None


@router.post("/login")
async def login(body: LoginRequest):
    if body.password != settings.admin_password:
        raise HTTPException(status_code=401, detail="Invalid password")
    token = create_access_token({"sub": "admin", "role": "admin"})
    return {"access_token": token, "token_type": "bearer"}


@router.get("/conversations")
async def list_conversations(
    page: int = 1,
    page_size: int = 20,
    search: Optional[str] = None,
    has_email: Optional[bool] = None,
    current_admin: dict = Depends(get_current_admin),
    db: Session = Depends(get_session),
):
    stmt = select(ChatSession).order_by(ChatSession.started_at.desc())
    if has_email is True:
        stmt = stmt.where(ChatSession.user_email != None)
    if has_email is False:
        stmt = stmt.where(ChatSession.user_email == None)

    sessions = db.exec(stmt).all()

    if search:
        search_lower = search.lower()
        msgs = db.exec(
            select(ChatMessage).where(ChatMessage.content.ilike(f"%{search}%"))
        ).all()
        matching_ids = {m.session_id for m in msgs}
        sessions = [
            s for s in sessions
            if s.id in matching_ids
            or (s.user_email and search_lower in s.user_email.lower())
            or (s.user_name and search_lower in s.user_name.lower())
        ]

    total = len(sessions)
    offset = (page - 1) * page_size
    page_sessions = sessions[offset: offset + page_size]

    return {
        "sessions": [
            {
                "id": s.id,
                "started_at": s.started_at.isoformat(),
                "last_active": s.last_active.isoformat(),
                "message_count": s.message_count,
                "user_email": s.user_email,
                "user_name": s.user_name,
                "page_url": s.page_url,
                "ip_address": s.ip_address,
            }
            for s in page_sessions
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/conversations/{session_id}")
async def get_conversation(
    session_id: str,
    current_admin: dict = Depends(get_current_admin),
    db: Session = Depends(get_session),
):
    chat_session = db.exec(
        select(ChatSession).where(ChatSession.id == session_id)
    ).first()
    if not chat_session:
        raise HTTPException(status_code=404, detail="Session not found")

    messages = db.exec(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.timestamp)
    ).all()

    return {
        "session": {
            "id": chat_session.id,
            "started_at": chat_session.started_at.isoformat(),
            "last_active": chat_session.last_active.isoformat(),
            "user_email": chat_session.user_email,
            "user_name": chat_session.user_name,
            "page_url": chat_session.page_url,
            "ip_address": chat_session.ip_address,
            "message_count": chat_session.message_count,
        },
        "messages": [
            {
                "role": m.role,
                "content": m.content,
                "timestamp": m.timestamp.isoformat(),
                "suggested_url": m.suggested_url,
                "suggested_title": m.suggested_title,
            }
            for m in messages
        ],
    }


@router.get("/users")
async def list_users(
    page: int = 1,
    page_size: int = 50,
    current_admin: dict = Depends(get_current_admin),
    db: Session = Depends(get_session),
):
    users = db.exec(
        select(CollectedUser).order_by(CollectedUser.collected_at.desc())
    ).all()
    total = len(users)
    offset = (page - 1) * page_size
    return {
        "users": [
            {
                "id": u.id,
                "email": u.email,
                "name": u.name,
                "query": u.query,
                "page_url": u.page_url,
                "collected_at": u.collected_at.isoformat(),
                "session_id": u.session_id,
            }
            for u in users[offset: offset + page_size]
        ],
        "total": total,
    }


@router.get("/settings")
async def get_settings_endpoint(current_admin: dict = Depends(get_current_admin)):
    keys = [
        "admin_email", "smtp_host", "smtp_port", "smtp_user",
        "smtp_from_name", "chatbot_name", "chatbot_greeting",
        "auto_email_transcripts", "email_notifications_enabled",
    ]
    result = {k: get_admin_config(k, "") for k in keys}
    result["smtp_password"] = "***" if get_admin_config("smtp_password") else ""
    return result


@router.post("/settings")
async def update_settings(
    body: SettingsUpdate,
    current_admin: dict = Depends(get_current_admin),
):
    data = body.model_dump(exclude_none=True)
    for key, value in data.items():
        if key == "smtp_password" and value == "***":
            continue
        set_admin_config(key, value)
    return {"success": True}


@router.post("/scrape")
async def trigger_scrape(
    background_tasks: BackgroundTasks,
    current_admin: dict = Depends(get_current_admin),
):
    """Trigger full website re-scrape and re-index in the background."""
    if _scrape_status["running"]:
        return {"success": False, "message": "Scrape already in progress"}

    async def run_scrape():
        _scrape_status["running"] = True
        try:
            result = await scrape_and_index()
            await index_chunks(result["chunks"])
            _scrape_status["last_result"] = {
                "total_pages": len(result["pages"]),
                "total_chunks": result["total_chunks"],
                "completed_at": datetime.utcnow().isoformat(),
            }
        except Exception as e:
            print(f"[Scrape] Error: {e}")
            _scrape_status["last_result"] = {"error": str(e)}
        finally:
            _scrape_status["running"] = False
            _scrape_status["last_run"] = datetime.utcnow().isoformat()

    background_tasks.add_task(run_scrape)
    return {"success": True, "message": "Scrape started in the background. This may take 2–5 minutes."}


@router.get("/scrape-status")
async def get_scrape_status(current_admin: dict = Depends(get_current_admin)):
    return {
        "running": _scrape_status["running"],
        "last_run": _scrape_status["last_run"],
        "last_result": _scrape_status["last_result"],
        "indexed_chunks": get_collection_count(),
    }


@router.get("/content-pages")
async def list_content_pages(
    current_admin: dict = Depends(get_current_admin),
    db: Session = Depends(get_session),
):
    pages = db.exec(
        select(ContentChunk).order_by(ContentChunk.last_scraped.desc())
    ).all()
    return {
        "pages": [
            {
                "url": p.url,
                "title": p.title,
                "chunk_count": p.chunk_count,
                "status": p.status,
                "last_scraped": p.last_scraped.isoformat() if p.last_scraped else None,
            }
            for p in pages
        ]
    }
