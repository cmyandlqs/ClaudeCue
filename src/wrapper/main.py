"""cc-wrapper 入口 — Claude Code 启动包装器。"""

import argparse
import sys
from pathlib import Path

# 将项目根目录加入 sys.path
ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from src.common.config import load_app_config, load_rules
from src.common.logger import setup_logger
from src.wrapper.client import NotifierClient
from src.wrapper.event_detector import EventDetector
from src.wrapper.launcher import Launcher
from src.wrapper.rule_engine import RuleEngine
from src.wrapper.stream_reader import StreamReader


def main():
    parser = argparse.ArgumentParser(description="Claude Code 提醒助手 — 包装启动器")
    parser.add_argument("args", nargs="*", help="传递给 Claude Code 的额外参数")
    parser.add_argument("--cwd", default=None, help="工作目录")
    parser.add_argument("--config", default=None, help="配置文件路径")
    parser.add_argument("--rules", default=None, help="规则配置文件路径")
    opts = parser.parse_args()

    # 加载配置
    config_path = opts.config or str(ROOT / "config" / "app.yaml")
    config = load_app_config(config_path)

    rules_path = opts.rules or str(ROOT / "config" / "rules.yaml")
    custom_rules = load_rules(rules_path)

    logger = setup_logger("wrapper", config.logging.level, config.logging.dir)

    # 初始化组件
    client = NotifierClient(config)
    client.check_health()

    rule_engine = RuleEngine(custom_rules=custom_rules)

    # 启动 Claude Code
    launcher = Launcher(config, cwd=opts.cwd)
    try:
        launcher.start(extra_args=opts.args)
    except FileNotFoundError:
        logger.error("找不到 claude 命令，请确认已安装 Claude Code CLI")
        sys.exit(1)

    # 初始化事件检测器
    detector = EventDetector(
        config=config,
        client=client,
        rule_engine=rule_engine,
        session_id=launcher.session_id,
        process_id=launcher.pid,
        cwd=launcher.cwd,
    )

    # 发送启动事件
    client.send_event(launcher.build_started_event())

    # 输出监听回调
    def on_line(line: str, source: str):
        # 将每行透传到终端（保持原样输出）
        if source == "stdout":
            sys.stdout.write(line + "\n")
            sys.stdout.flush()
        else:
            sys.stderr.write(line + "\n")
            sys.stderr.flush()

        # 送入事件检测器
        detector.process_line(line, source)

    # 空闲监控回调
    def on_idle_check():
        detector.check_idle(reader.idle_seconds)

    # 启动流读取
    reader = StreamReader(
        launcher.process,
        on_line=on_line,
        on_idle_check=on_idle_check,
        idle_interval=float(config.idle.suspected_after_sec) / 12,
    )
    reader.start()

    # 等待进程结束
    exit_code = launcher.wait()
    reader.stop()
    detector.mark_exited()

    # 发送退出事件
    client.send_event(launcher.build_exited_event(exit_code))
    logger.info("Claude Code 已退出: code=%d", exit_code)

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
