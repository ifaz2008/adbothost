from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import ad_rewards, admin, auth, bots, coupons, credits, deployments, logs, payment_requests, plans, users, worker_nodes
from app.core.config import settings
from app.db.session import init_db
from app.scheduler.jobs import create_scheduler, refresh_worker_nodes
from app.services.plans import ensure_default_plans
from app.db.session import SessionLocal


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    db = SessionLocal()
    try:
        ensure_default_plans(db)
    finally:
        db.close()
    scheduler = None
    if settings.scheduler_enabled:
        scheduler = create_scheduler()
        scheduler.start()
        try:
            refresh_worker_nodes()
        except Exception:
            pass
    yield
    if scheduler:
        scheduler.shutdown(wait=False)


app = FastAPI(
    title="AdBotHost API",
    description="Secure lightweight hosting for small Telegram bots only.",
    version="0.1.0",
    root_path=settings.api_root_path,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(plans.router)
app.include_router(bots.router)
app.include_router(deployments.router)
app.include_router(credits.router)
app.include_router(payment_requests.router)
app.include_router(coupons.router)
app.include_router(logs.router)
app.include_router(worker_nodes.router)
app.include_router(ad_rewards.router)
app.include_router(admin.router)
app.include_router(payment_requests.admin_router)
app.include_router(coupons.admin_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "backend"}


@app.get("/")
def root() -> dict[str, str]:
    return {"service": "AdBotHost API", "docs": f"{settings.api_root_path or ''}/docs"}
