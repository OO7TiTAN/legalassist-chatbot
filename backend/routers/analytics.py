from fastapi import APIRouter, Depends
from sqlmodel import Session, select, func
from datetime import datetime, timedelta
from database import (
    ChatSession, ChatMessage, CollectedUser, TrafficEvent, get_session
)
from auth import get_current_admin
from collections import Counter
import re

router = APIRouter(prefix="/admin", tags=["analytics"])


@router.get("/analytics/overview")
async def get_overview(
    current_admin: dict = Depends(get_current_admin),
    db: Session = Depends(get_session),
):
    total_sessions = db.exec(select(func.count(ChatSession.id))).one()
    total_messages = db.exec(select(func.count(ChatMessage.id))).one()
    total_users = db.exec(select(func.count(CollectedUser.id))).one()
    total_pageviews = db.exec(select(func.count(TrafficEvent.id))).one()
    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    sessions_today = db.exec(
        select(func.count(ChatSession.id)).where(ChatSession.started_at >= today)
    ).one()
    avg_messages = round(total_messages / total_sessions, 1) if total_sessions > 0 else 0
    return {
        "total_sessions": total_sessions,
        "total_messages": total_messages,
        "total_users_collected": total_users,
        "total_pageviews": total_pageviews,
        "sessions_today": sessions_today,
        "avg_messages_per_session": avg_messages,
    }


@router.get("/analytics/daily-sessions")
async def get_daily_sessions(
    days: int = 30,
    current_admin: dict = Depends(get_current_admin),
    db: Session = Depends(get_session),
):
    cutoff = datetime.utcnow() - timedelta(days=days)
    sessions = db.exec(
        select(ChatSession)
        .where(ChatSession.started_at >= cutoff)
        .order_by(ChatSession.started_at)
    ).all()
    daily: dict = {}
    for s in sessions:
        key = s.started_at.strftime("%Y-%m-%d")
        daily[key] = daily.get(key, 0) + 1
    result = []
    for i in range(days):
        date = (datetime.utcnow() - timedelta(days=days - 1 - i)).strftime("%Y-%m-%d")
        result.append({"date": date, "count": daily.get(date, 0)})
    return result


@router.get("/analytics/top-queries")
async def get_top_queries(
    limit: int = 15,
    current_admin: dict = Depends(get_current_admin),
    db: Session = Depends(get_session),
):
    user_msgs = db.exec(
        select(ChatMessage.content)
        .where(ChatMessage.role == "user")
        .order_by(ChatMessage.timestamp.desc())
        .limit(500)
    ).all()
    word_counts: Counter = Counter()
    for msg in user_msgs:
        clean = re.sub(r'[^\w\s]', '', msg.lower()).strip()
        words = clean.split()
        if len(words) >= 2:
            phrase = " ".join(words[:4])
            word_counts[phrase] += 1
    top = word_counts.most_common(limit)
    return [{"query": q, "count": c} for q, c in top]


@router.get("/analytics/traffic")
async def get_traffic(
    days: int = 30,
    current_admin: dict = Depends(get_current_admin),
    db: Session = Depends(get_session),
):
    cutoff = datetime.utcnow() - timedelta(days=days)
    events = db.exec(
        select(TrafficEvent).where(TrafficEvent.timestamp >= cutoff)
    ).all()
    page_counts: Counter = Counter(ev.page_url for ev in events)
    return [{"url": url, "views": count} for url, count in page_counts.most_common(20)]


@router.get("/analytics/hourly-traffic")
async def get_hourly_traffic(
    days: int = 7,
    current_admin: dict = Depends(get_current_admin),
    db: Session = Depends(get_session),
):
    cutoff = datetime.utcnow() - timedelta(days=days)
    events = db.exec(
        select(TrafficEvent).where(TrafficEvent.timestamp >= cutoff)
    ).all()
    hourly = [0] * 24
    for ev in events:
        hourly[ev.timestamp.hour] += 1
    return [{"hour": h, "count": c} for h, c in enumerate(hourly)]
