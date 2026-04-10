"""HTTP 事件发送客户端 — 向 notifier-app 发送标准事件。"""

from __future__ import annotations

import time
from typing import Optional

import requests

from src.common.config import AppConfig
from src.common.constants import HTTP_MAX_RETRIES, HTTP_TIMEOUT_SEC
from src.common.logger import setup_logger
from src.common.models import EventObject

logger = setup_logger("wrapper.client")


class NotifierClient:
    """向 notifier-app 发送事件的 HTTP 客户端。"""

    def __init__(self, config: AppConfig):
        self.base_url = f"http://{config.server.host}:{config.server.port}"
        self._available: Optional[bool] = None

    def check_health(self) -> bool:
        """检查 notifier-app 是否在线。"""
        try:
            resp = requests.get(f"{self.base_url}/health", timeout=HTTP_TIMEOUT_SEC)
            self._available = resp.status_code == 200
        except requests.RequestException:
            self._available = False
            logger.warning("notifier-app 不可用，事件将仅写本地日志")
        return self._available

    def send_event(self, event: EventObject) -> bool:
        """发送事件，失败时有限重试。"""
        if self._available is None:
            self.check_health()

        if not self._available:
            logger.info("事件(未发送): type=%s title=%s", event.event_type.value, event.title)
            return False

        event.timestamps.sent_at = time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime())
        payload = event.to_dict()

        for attempt in range(1, HTTP_MAX_RETRIES + 1):
            try:
                resp = requests.post(
                    f"{self.base_url}/events",
                    json=payload,
                    timeout=HTTP_TIMEOUT_SEC,
                )
                if resp.status_code == 200:
                    logger.info("事件已发送: type=%s id=%s", event.event_type.value, event.event_id)
                    return True
            except requests.RequestException as e:
                logger.warning("发送失败(第%d次): %s", attempt, e)

        logger.warning("事件发送最终失败: type=%s", event.event_type.value)
        self._available = False
        return False
