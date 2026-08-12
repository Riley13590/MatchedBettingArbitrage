from __future__ import annotations

from datetime import UTC, datetime

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from apps.api.routes import events, markets, opportunities, orders, portfolio, venues
from apps.api.routes import settings as settings_routes
from marketedge.config.settings import get_settings
from marketedge.observability.logging import configure_logging

settings = get_settings()
configure_logging(settings.log_level, service="api")

app = FastAPI(title="MarketEdge UK API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(venues.router)
app.include_router(events.router)
app.include_router(markets.router)
app.include_router(opportunities.router)
app.include_router(orders.router)
app.include_router(portfolio.router)
app.include_router(settings_routes.router)


class HealthOut(BaseModel):
    status: str
    mode: str
    time_utc: datetime


@app.get("/v1/health", response_model=HealthOut, tags=["system"])
async def health() -> HealthOut:
    return HealthOut(status="ok", mode=settings.app_mode, time_utc=datetime.now(UTC))
