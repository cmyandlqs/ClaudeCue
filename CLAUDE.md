# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Claude Code 提醒助手 — 一个 Windows 桌面通知工具，在 Claude Code 后台运行时主动提醒用户（权限拦截、任务完成、等待输入等）。平台为 Windows + Windows Terminal。

## Architecture

双进程架构，通过本地 HTTP 通信：

```
cc-wrapper (监听进程)          notifier-app (常驻桌面进程)
├── launcher.py  启动 Claude Code     ├── server.py    HTTP 服务 (POST /events, GET /health)
├── stream_reader.py  读取 stdout/stderr  ├── overlay.py   置顶悬浮窗
├── event_detector.py  状态机+去重       ├── tray.py      系统托盘
├── rule_engine.py  规则匹配           ├── sound.py     提醒声音
├── client.py  HTTP 发送事件          └── window_focus.py  终端窗口聚焦
└── main.py
```

- `src/common/` — 共享模型（事件类型、级别）、配置、日志、常量
- `src/wrapper/` — Claude Code 包装启动器，负责进程管理和输出监听
- `src/notifier/` — 常驻 PySide6 桌面程序，负责悬浮提醒、托盘、声音、窗口聚焦
- `config/` — YAML 配置文件（`app.yaml` + `rules.yaml`）
- `src/tests/` — 单元测试和集成测试

## Tech Stack

- Python 3.x + PySide6
- 本地 HTTP 通信（默认 `127.0.0.1:45872`）
- 配置格式：YAML

## Key Design Decisions

- **事件模型**：所有模块间传递标准事件对象（含 event_id、event_type、severity、timestamps），禁止传裸字符串
- **事件类型**：`task_completed` | `needs_input` | `permission_blocked` | `error_detected` | `idle_timeout` | `process_started` | `process_exited`
- **严重级别**：`info`（自动消失）| `warning`（停留）| `critical`（置顶常驻）
- **规则引擎**：基于 `contains` / `regex` / `any_of` 匹配，规则可配置，内置默认规则 + 外部 `rules.yaml` 覆盖
- **去重**：同 event_type 30 秒内只提醒一次，状态切换后允许再次提醒
- **降级**：notifier 未启动时 wrapper 仅写本地日志不阻断；HTTP 发送失败有限重试后降级

## Event Object Structure

```json
{
  "event_id": "uuid",
  "event_type": "permission_blocked",
  "severity": "critical",
  "title": "...",
  "message": "...",
  "source": "cc-wrapper",
  "session_id": "...",
  "process_id": 12345,
  "terminal_hint": { "window_title": "...", "cwd": "..." },
  "match": { "rule_id": "...", "pattern": "...", "sample_text": "..." },
  "timestamps": { "occurred_at": "...", "sent_at": "..." },
  "display": { "sticky": true, "play_sound": true, "timeout_ms": 0 }
}
```

## Running

```bash
# 1. 先启动 notifier 常驻程序
python src/notifier/main.py

# 2. 再通过 wrapper 启动 Claude Code
python src/wrapper/main.py
```

## API Endpoints (notifier-app)

- `POST /events` — 接收标准事件
- `GET /health` — 健康检查
- `POST /focus` — 调试终端聚焦

## Development Milestones

- **M1**：基础骨架（notifier HTTP 服务 + 测试悬浮窗）
- **M2**：包装器与事件发送（启动 Claude Code + 输出监听 + 事件上报）
- **M3**：规则识别 MVP（task_completed / needs_input / permission_blocked + 去重）
- **M4**：增强提醒（error_detected / idle_timeout / 声音 / 点击返回终端）

## Reference Docs

- `需求.md` — 原始需求
- `方案设计.md` — 多方案对比与选型依据
- `第一阶段开发文档.md` — 完整的第一阶段设计文档（模块职责、接口、状态机、配置、测试计划）
