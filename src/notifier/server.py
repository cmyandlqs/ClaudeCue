"""notifier HTTP 服务 — FastAPI，提供 /events、/health、/focus 接口。"""

from __future__ import annotations

import threading
from typing import Callable, Optional

import uvicorn
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from src.common.config import AppConfig
from src.common.logger import setup_logger

logger = setup_logger("notifier.server")

# ── Pydantic 请求模型 ──────────────────────────────────────────

class EventRequest(BaseModel):
    event_id: str
    event_type: str
    severity: str
    title: str = ""
    message: str = ""
    source: str = "cc-wrapper"
    session_id: str = ""
    process_id: int = 0
    terminal_hint: dict = {}
    match: dict = {}
    timestamps: dict = {}
    display: dict = {}


class FocusRequest(BaseModel):
    window_title: str = ""
    cwd: str = ""


# ── 应用工厂 ──────────────────────────────────────────────────

def create_app(
    on_event: Optional[Callable[[dict], None]] = None,
    on_focus: Optional[Callable[[dict], None]] = None,
) -> FastAPI:
    app = FastAPI(title="claudecode-notifier")

    @app.get("/health")
    def health():
        return {"ok": True, "service": "notifier-app"}

    @app.post("/events")
    def receive_event(event: EventRequest):
        data = event.model_dump()
        logger.info("收到事件: type=%s severity=%s title=%s",
                     data["event_type"], data["severity"], data["title"])
        if on_event:
            on_event(data)
        return {"ok": True, "accepted": True}

    @app.post("/focus")
    def focus_terminal(req: FocusRequest):
        logger.info("聚焦请求: title=%s cwd=%s", req.window_title, req.cwd)
        if on_focus:
            on_focus(req.model_dump())
        return {"ok": True}

    return app


# ── 线程启动器 ──────────────────────────────────────────────────

class ServerThread(threading.Thread):
    """在后台线程中运行 uvicorn。"""

    def __init__(self, config: AppConfig,
                 on_event: Optional[Callable[[dict], None]] = None,
                 on_focus: Optional[Callable[[dict], None]] = None):
        super().__init__(daemon=True)
        self.config = config
        self.app = create_app(on_event=on_event, on_focus=on_focus)

    def run(self):
        uvicorn.run(
            self.app,
            host=self.config.server.host,
            port=self.config.server.port,
            log_level="warning",
        )
