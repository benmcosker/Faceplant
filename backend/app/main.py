from contextlib import asynccontextmanager
from pathlib import Path

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI, Request
from fastapi.exceptions import HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .bots.origination import run_bot_origination
from .bots.reactions import run_due_reaction_jobs
from .config import settings
from .db import Base, engine, ensure_columns
from .routers import admin_bots, ads, comments, costs, likes, posts, users

Base.metadata.create_all(engine)
# Self-heal databases created before later columns were added (e.g. users.mood).
ensure_columns()

Path(settings.media_root, "avatars").mkdir(parents=True, exist_ok=True)

scheduler = AsyncIOScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler.add_job(run_due_reaction_jobs, "interval", seconds=20)
    # Phase 3: occasionally a bot posts on its own (no-op unless enabled).
    scheduler.add_job(run_bot_origination, "interval", seconds=60)
    scheduler.start()
    yield
    scheduler.shutdown(wait=False)


app = FastAPI(title="Faceplant", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/media", StaticFiles(directory=settings.media_root), name="media")

app.include_router(users.router)
app.include_router(posts.router)
app.include_router(comments.router)
app.include_router(likes.router)
app.include_router(admin_bots.router)
app.include_router(ads.router)
app.include_router(costs.router)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Consistent error shape: {error, code, status}."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail, "code": "http_error", "status": exc.status_code},
    )


@app.get("/api/health")
def health():
    return {"status": "ok"}
