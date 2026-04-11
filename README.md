# ccCue

[English README](./README.en.md)

Windows desktop notification and terminal refocus helper for Claude Code.

> 平台限制：当前仅支持 Windows 10/11。

## 项目简介

ccCue 通过 Claude Hooks 接收事件，在 Windows 桌面展示通知，并支持一键回焦终端窗口。  
目标是让你在终端不在前台时，依然不会错过任务完成、权限请求等关键状态。

## 核心特性

- Hooks 事件链路：`hooks -> bootstrap -> notifier`
- 通知展示：浮层 + 托盘 + 声音
- 回焦能力：通知点击 + 全局快捷键
- 安全配置：`settings.json` 备份 / 校验 / 回滚 / 恢复
- CLI 能力：`install / uninstall / doctor / restore / list-backups`

## 架构

```text
Claude hooks (stdin JSON)
  -> hooks/bootstrap.py
  -> hooks/notify_hook.py
  -> notifier/server.py (/event)
  -> notifier UI (overlay / tray / focus-back)
```

## 安装

### 方式 A：EXE 安装（普通用户）

1. 下载 Release 中的 `ccCue-Setup-*.exe`
2. 双击安装
3. 可修改安装目录（例如 `D:\Apps\ccCue`）

说明：
- 当前仓库中的安装器脚本仍检查 Python 可用性。
- 项目路线图已确定逐步过渡到不依赖用户 Python 的独立运行时。

### 方式 B：源码一键安装（开发者）

```bash
git clone https://github.com/cmyandlqs/ClaudeCue.git
cd ClaudeCue
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m cli.main install --source . --target "%LOCALAPPDATA%\ccCue"
```

安装到 D 盘示例：

```bash
.venv\Scripts\python -m cli.main install --source . --target "D:\Apps\ccCue"
```

## 日常使用

1. 正常运行 Claude Code
2. 有事件时 ccCue 自动接收并弹通知
3. 点击通知或用快捷键回到终端

## 诊断与恢复

```bash
.venv\Scripts\python -m cli.main doctor
.venv\Scripts\python -m cli.main doctor --json
.venv\Scripts\python -m cli.main restore --latest
.venv\Scripts\python -m cli.main uninstall --purge
```

`doctor` 当前支持 `PASS / WARN / FAIL` 分级，并在失败项中输出修复建议。

## 开发

```bash
.venv\Scripts\python -m ruff check cli config tests
.venv\Scripts\python -m vulture cli config tests --min-confidence 80
.venv\Scripts\python -m pytest -q
```


## 路线图（摘要）

- 运行时独立化（减少对用户机器 Python 依赖）
- 发布流程标准化（构建/验收/回滚）
- 诊断可读性与回焦稳定性持续优化

---

如果 ccCue 对你有帮助，别让它在星海里孤单漂流，顺手点个 Star 吧 ✨

