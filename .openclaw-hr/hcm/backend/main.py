"""FastAPI application entry point."""

import json
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from database import engine, Base
from routers import candidates
from websocket import manager
from sqlalchemy import inspect, text


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create database tables on startup; drop leftover reviews table."""
    Base.metadata.create_all(bind=engine)
    inspector = inspect(engine)
    if "reviews" in inspector.get_table_names():
        with engine.begin() as conn:
            conn.execute(text("DROP TABLE IF EXISTS reviews"))
    yield


app = FastAPI(
    title="HCM 入职管理系统",
    description="模拟 HCM 数据源 — 各部门填写入职准备数据，小慧 GET 只读查询",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS — allow frontend dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register REST routers
app.include_router(candidates.router)


@app.websocket("/ws/dashboard")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time dashboard updates."""
    await manager.connect(websocket)
    try:
        while True:
            # Keep connection alive; client may send pings
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)


@app.get("/api/health")
def health():
    return {"ok": True, "service": "hcm"}
