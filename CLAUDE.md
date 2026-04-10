# CLAUDE.md

## 项目概述

ccCue 是 Claude Code 的 Windows 辅助通知工具，核心提供：

1. 桌面通知（优先）
2. 终端回焦

## 架构原则

1. 放弃 wrapper，采用 Claude Hooks。
2. Claude 保持原生终端运行。
3. hooks 与 UI 责任分离。

## 当前目录结构（关键）

```text
ccCue/
├─ hooks/
│  ├─ bootstrap.py
│  └─ notify_hook.py
├─ notifier/
│  ├─ main.py
│  ├─ single_instance.py
│  └─ ...
├─ config/
│  ├─ state_manager.py
│  └─ settings.example.json
├─ cli/
│  └─ main.py
├─ installer/
│  ├─ install.bat
│  ├─ uninstall.bat
│  ├─ ccCue.iss
│  └─ build_inno.bat
└─ tests/
```

## 当前实现状态（2026-04-10）

1. hooks 自动拉起 notifier 已完成。
2. notifier 单实例已完成。
3. 配置安全写入/恢复已完成。
4. CLI 已完成。
5. Inno Setup 打包链路已完成。
6. 自动化测试通过（35 passed）。

## 运维命令

1. 安装/更新：`python -m cli.main install --project-root <path>`
2. 卸载：`python -m cli.main uninstall`
3. 健康检查：`python -m cli.main doctor --json`
4. 恢复：`python -m cli.main restore --latest`

## 重要约束

1. 修改代码前后需保持本文档与 `需求.md/方案设计.md/阶段文档`一致。
2. 配置写入必须优先保证用户 `settings.json` 安全。
3. 不允许回退到 wrapper 方案。
