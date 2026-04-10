"""常量定义：事件类型、严重级别、默认配置值。"""

from enum import Enum


class EventType(str, Enum):
    TASK_COMPLETED = "task_completed"
    NEEDS_INPUT = "needs_input"
    PERMISSION_BLOCKED = "permission_blocked"
    ERROR_DETECTED = "error_detected"
    IDLE_TIMEOUT = "idle_timeout"
    PROCESS_STARTED = "process_started"
    PROCESS_EXITED = "process_exited"


class Severity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class SessionState(str, Enum):
    RUNNING = "running"
    WAITING_INPUT = "waiting_input"
    WAITING_PERMISSION = "waiting_permission"
    IDLE_SUSPECTED = "idle_suspected"
    COMPLETED = "completed"
    EXITED = "exited"


# 事件类型 → 严重级别 默认映射
EVENT_SEVERITY_MAP = {
    EventType.TASK_COMPLETED: Severity.INFO,
    EventType.NEEDS_INPUT: Severity.WARNING,
    EventType.PERMISSION_BLOCKED: Severity.CRITICAL,
    EventType.ERROR_DETECTED: Severity.CRITICAL,
    EventType.IDLE_TIMEOUT: Severity.WARNING,
    EventType.PROCESS_STARTED: Severity.INFO,
    EventType.PROCESS_EXITED: Severity.INFO,
}

# 默认服务端口
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 45872

# 去重间隔（秒）
DEDUP_INTERVAL_SEC = 30

# 空闲超时默认值（秒）
IDLE_SUSPECTED_SEC = 60
IDLE_NOTIFY_SEC = 120

# HTTP client 配置
HTTP_TIMEOUT_SEC = 2
HTTP_MAX_RETRIES = 3

# 悬浮窗默认值
OVERLAY_WIDTH = 360
OVERLAY_HEIGHT = 120
OVERLAY_OPACITY = 0.96
