# CLAUDE.md

## 项目概述

ccCue 是为 Claude Code 开发的 Windows 平台辅助工具，核心目标是提供：

1. **终端侧的对话历史导航能力**（第二优先级）
2. **全局置顶的桌面提醒层**（第一优先级）

当前聚焦于第 2 项：在 Claude Code 后台运行、任务完成、等待输入、权限拦截等时机及时唤醒用户。

## 平台约束

- **仅支持 Windows 平台**
- **主运行环境：Windows Terminal**

## 架构决策：放弃 Wrapper，采用 Hooks

### 已废弃的方案

原先的 `wrapper` 方案已确认不可行：

```text
wrapper -> 启动 claude -> 接管 stdout/stderr -> 规则匹配 -> 通知 UI
```

**失败原因**：
- Claude Code 是交互式 CLI，需要真实 TTY
- `subprocess.Popen(stdout=PIPE, stderr=PIPE)` 会剥离终端交互环境
- 在这种模式下，Claude Code 无法作为正常工作流稳定运行
- 这不是小修小补能解决的问题

### 新架构：基于 Claude Code 原生 Hooks

```text
Claude Code 正常运行
  -> 官方 hooks 触发
  -> 本地 hook 脚本读取 stdin JSON
  -> 统一事件格式
  -> POST 到 notifier-app
  -> notifier-app 展示悬浮窗 / 托盘 / 声音 / 聚焦
```

## 项目结构

```
ccCue/
├── hooks/               # Claude Code hook 脚本
│   └── notify_hook.py   # 读取 hook JSON，转发到 notifier
├── notifier/            # 桌面展示层
│   ├── main.py          # 入口
│   ├── server.py        # 本地 HTTP 接口
│   ├── overlay.py       # 悬浮提醒窗
│   ├── tray.py          # 系统托盘
│   ├── sound.py         # 提示音
│   └── window_focus.py  # 聚焦终端
├── installer/           # Windows 安装脚本
│   └── install.bat      # 一键配置
├── 需求.md              # 项目需求
├── 方案设计.md          # 架构设计
├── 第一阶段开发文档.md   # 开发计划
└── AGENTS.md            # Agent 指引
```

## 核心组件职责

### 1. Hook 层 (`hooks/`)

**职责**：
- 接收 Claude Code hook payload（通过 stdin）
- 将不同 hook 事件映射成统一事件模型
- 调用本地 HTTP 接口转发给 notifier

**不负责**：
- 长生命周期 UI
- 复杂状态持有
- 终端进程控制

### 2. Notifier 展示层 (`notifier/`)

**职责**：
- 常驻后台进程
- 提供本地 HTTP 接口接收 hook 事件
- 展示悬浮提醒
- 托盘驻留
- 播放提示音
- 支持点击后聚焦回 Windows Terminal

### 3. 安装与配置层 (`installer/`)

**职责**：
- 写入或引导用户更新 `~/.claude/settings.json`
- 注册 `Notification`、`Stop` 等 hooks
- 提供 Windows 友好的一键配置脚本

## 统一事件模型

Hook 层与 notifier 层之间采用统一的 JSON 格式：

```json
{
  "event_id": "uuid",
  "event_type": "needs_input",
  "severity": "warning",
  "title": "Claude Code 等待输入",
  "message": "请回到终端继续交互",
  "source": "claude-hook",
  "session_id": "",
  "timestamps": {
    "occurred_at": ""
  },
  "display": {
    "sticky": true,
    "play_sound": true,
    "timeout_ms": 0
  }
}
```

## 第一阶段开发计划

### 目标

形成可运行的最小闭环：

```text
Claude Code hooks
  -> hook 转发脚本
  -> notifier 本地 HTTP 服务
  -> 悬浮提醒展示
```

### 里程碑

#### M1: 协议与 hooks 配置
- 整理 Claude hooks 事件
- 确认统一事件模型
- 形成 settings.json 配置样例

#### M2: Hook 转发脚本
- 从 stdin 读取 hook payload
- 映射为本地统一事件
- POST 到 notifier 本地服务

#### M3: Notifier MVP
- 本地 HTTP 接口
- 悬浮提醒
- 托盘与声音

#### M4: Windows 安装体验
- 一键安装脚本
- 配置落盘
- 运行说明与排错说明

### 明确不做

以下内容不再属于第一阶段实现范围：
- wrapper 启动 Claude
- stdout/stderr 抓取
- 基于终端文本规则匹配事件
- 伪终端或兼容性补丁式方案

## 推荐的 Hook 事件

第一阶段优先支持：
- `notification` - 通知消息
- `stop` - 任务停止
- `permission_required` - 权限请求
- `needs_input` - 等待用户输入

后续可扩展：
- `pre_tool_use` / `post_tool_use`
- 更细粒度的任务阶段事件

## 开发规则

1. **代码与文档同步**：如果代码和文档不一致，优先更新文档
2. **职责分离**：不耦合 hook 解析直接到 UI 组件
3. **本地通信**：使用 localhost HTTP 在 hooks 和 notifier 之间通信
4. **小步提交**：使用架构范围的小提交，如 `docs: switch plan to hooks` 或 `feat: add notification hook bridge`

## 测试策略

第一阶段测试重点：
1. hook payload 到统一事件的映射测试
2. notifier HTTP 接口测试
3. 展示层的非 GUI 逻辑测试
4. Windows 配置脚本的手工验证

## 当前状态

- 旧 wrapper 实现已删除
- 仓库处于文档驱动的重置状态
- 下一轮实现将基于 hook 架构从零开始
- 不复用 wrapper 模块
