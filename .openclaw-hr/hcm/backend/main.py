"""FastAPI application entry point."""

from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from routers import candidates, reports, nodes
from websocket import manager
from schema_migrate import migrate_schema


@asynccontextmanager
async def lifespan(app: FastAPI):
    """建表，并丢掉旧月度宽表 / 整包 payload_json。"""
    migrate_schema()
    yield


app = FastAPI(
    title="HCM 入职管理系统",
    description="HCM：花名册、入职准备节点、日常业务事实与只读冻结月报。月报数字由事实计算后写入主题快照。",
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
app.include_router(reports.router)
app.include_router(nodes.router)


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
