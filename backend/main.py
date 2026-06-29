import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
import os

from config import get_settings
from database import create_db_and_tables, seed_default_config
from embeddings import get_collection_count
from scraper import scrape_and_index
from embeddings import index_chunks
from routers import chat, admin, analytics

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: init DB, seed config, auto-index if needed."""
    print("[Startup] Initialising database...")
    create_db_and_tables()
    seed_default_config()
    print("[Startup] Database ready.")

    # Auto-scrape if ChromaDB is empty
    chunk_count = get_collection_count()
    if chunk_count == 0:
        print("[Startup] No content indexed. Running initial scrape (this may take a few minutes)...")
        try:
            result = await scrape_and_index()
            await index_chunks(result["chunks"])
            print(f"[Startup] Indexed {result['total_chunks']} chunks from {len(result['pages'])} pages.")
        except Exception as e:
            print(f"[Startup] Initial scrape failed: {e}. You can trigger it manually from the Admin Dashboard.")
    else:
        print(f"[Startup] ChromaDB has {chunk_count} chunks already indexed.")

    yield
    print("[Shutdown] Cleaning up...")


app = FastAPI(
    title="LegalAssist Chatbot API",
    description="AI-powered chatbot backend for legalassistglobal.com",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.app_env != "production" else None,
    redoc_url=None,
)

# CORS — allow WordPress origin + admin dashboard
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origins_list + ["*"],  # tighten in production
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# Mount admin dashboard as static files
admin_dashboard_path = os.path.join(os.path.dirname(__file__), "..", "admin-dashboard")
if os.path.exists(admin_dashboard_path):
    app.mount("/admin-ui", StaticFiles(directory=admin_dashboard_path, html=True), name="admin-ui")

# Register routers
app.include_router(chat.router)
app.include_router(admin.router)
app.include_router(analytics.router)


@app.get("/", tags=["health"])
async def root():
    return {
        "status": "ok",
        "service": "LegalAssist Chatbot API",
        "version": "1.0.0",
        "indexed_chunks": get_collection_count(),
    }


@app.get("/health", tags=["health"])
async def health():
    return {"status": "healthy"}
