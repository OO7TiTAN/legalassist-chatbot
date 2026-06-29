from fastapi import APIRouter, Depends, Request, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from sqlmodel import Session, select
from database import (
    ChatSession, ChatMessage, CollectedUser, TrafficEvent, get_session
)
from rag import chat as rag_chat
from email_service import send_user_query_email
import uuid

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    page_url: Optional[str] = None


class EmailRequest(BaseModel):
    session_id: str
    email: str
    name: Optional[str] = None
    query: Optional[str] = None
    page_url: Optional[str] = None


class PageViewRequest(BaseModel):
    session_id: Optional[str] = None
    page_url: str
    referrer: Optional[str] = None


def get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


@router.post("")
async def chat_endpoint(
    body: ChatRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_session),
):
    """Main chat endpoint — processes message through RAG pipeline."""
    if not body.message or len(body.message.strip()) < 2:
        raise HTTPException(status_code=400, detail="Message too short")
    if len(body.message) > 2000:
        raise HTTPException(status_code=400, detail="Message too long (max 2000 chars)")

    ip = get_client_ip(request)
    ua = request.headers.get("User-Agent", "")[:500]

    # Get or create session
    session_id = body.session_id
    chat_session = None
    if session_id:
        chat_session = db.exec(
            select(ChatSession).where(ChatSession.id == session_id)
        ).first()

    if not chat_session:
        session_id = str(uuid.uuid4())
        chat_session = ChatSession(
            id=session_id,
            ip_address=ip,
            user_agent=ua,
            page_url=body.page_url,
            started_at=datetime.utcnow(),
            last_active=datetime.utcnow(),
        )
        db.add(chat_session)
        db.commit()

    # Load conversation history
    history_msgs = db.exec(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.timestamp)
    ).all()
    history = [{"role": m.role, "content": m.content} for m in history_msgs]

    # Call RAG pipeline
    result = await rag_chat(
        user_message=body.message,
        conversation_history=history,
        session_page_url=body.page_url or chat_session.page_url,
    )

    # Persist messages
    db.add(ChatMessage(
        session_id=session_id, role="user",
        content=body.message, timestamp=datetime.utcnow(),
    ))
    db.add(ChatMessage(
        session_id=session_id, role="assistant",
        content=result["response"],
        suggested_url=result.get("suggested_url"),
        suggested_title=result.get("suggested_title"),
        timestamp=datetime.utcnow(),
    ))

    # Update session
    chat_session.last_active = datetime.utcnow()
    chat_session.message_count = (chat_session.message_count or 0) + 1
    if body.page_url and not chat_session.page_url:
        chat_session.page_url = body.page_url
    db.add(chat_session)
    db.commit()

    return {
        "session_id": session_id,
        "message": result["response"],
        "suggested_url": result.get("suggested_url"),
        "suggested_title": result.get("suggested_title"),
    }


@router.post("/collect-email")
async def collect_email(
    body: EmailRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_session),
):
    """Save user email + query, then notify admin."""
    existing = db.exec(
        select(CollectedUser).where(
            CollectedUser.session_id == body.session_id,
            CollectedUser.email == body.email,
        )
    ).first()

    if not existing:
        db.add(CollectedUser(
            session_id=body.session_id, email=body.email,
            name=body.name, query=body.query,
            page_url=body.page_url, collected_at=datetime.utcnow(),
        ))
        session = db.exec(
            select(ChatSession).where(ChatSession.id == body.session_id)
        ).first()
        if session:
            session.user_email = body.email
            session.user_name = body.name
            db.add(session)
        db.commit()

        background_tasks.add_task(
            send_user_query_email,
            user_email=body.email,
            user_name=body.name,
            query=body.query or "Not provided",
            page_url=body.page_url,
            session_id=body.session_id,
        )

    return {"success": True, "message": "Thank you! We'll be in touch shortly."}


@router.post("/pageview")
async def track_pageview(
    body: PageViewRequest,
    request: Request,
    db: Session = Depends(get_session),
):
    """Non-blocking page view tracker for analytics."""
    ip = get_client_ip(request)
    ua = request.headers.get("User-Agent", "")[:500]
    db.add(TrafficEvent(
        session_id=body.session_id, page_url=body.page_url,
        referrer=body.referrer, ip_address=ip,
        user_agent=ua, timestamp=datetime.utcnow(),
    ))
    db.commit()
    return {"success": True}


@router.get("/session/{session_id}")
async def get_session_history(session_id: str, db: Session = Depends(get_session)):
    """Retrieve conversation history for a session."""
    messages = db.exec(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.timestamp)
    ).all()
    return {"session_id": session_id, "messages": [
        {"role": m.role, "content": m.content,
         "timestamp": m.timestamp.isoformat(),
         "suggested_url": m.suggested_url,
         "suggested_title": m.suggested_title}
        for m in messages
    ]}
