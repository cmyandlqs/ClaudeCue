"""规则匹配引擎 — 支持 contains / regex / any_of 三种匹配方式。"""

from __future__ import annotations

import re
from typing import Optional

from src.common.config import RuleDefinition
from src.common.constants import EVENT_SEVERITY_MAP, EventType, Severity
from src.common.logger import setup_logger
from src.common.models import MatchInfo

logger = setup_logger("wrapper.rule_engine")

# ── 内置默认规则 ──────────────────────────────────────────────

BUILTIN_RULES: list[dict] = [
    {
        "id": "builtin.permission.01",
        "event_type": "permission_blocked",
        "severity": "critical",
        "match_type": "contains",
        "pattern": "Claude wants to",
        "applies_to": ["stdout", "stderr"],
    },
    {
        "id": "builtin.permission.02",
        "event_type": "permission_blocked",
        "severity": "critical",
        "match_type": "contains",
        "pattern": "Allow",
        "applies_to": ["stdout", "stderr"],
    },
    {
        "id": "builtin.permission.03",
        "event_type": "permission_blocked",
        "severity": "critical",
        "match_type": "contains",
        "pattern": "Deny",
        "applies_to": ["stdout", "stderr"],
    },
    {
        "id": "builtin.input.01",
        "event_type": "needs_input",
        "severity": "warning",
        "match_type": "regex",
        "pattern": r"(?i)(press enter|waiting for input|continue\?)",
        "applies_to": ["stdout", "stderr"],
    },
    {
        "id": "builtin.task.completed.01",
        "event_type": "task_completed",
        "severity": "info",
        "match_type": "regex",
        "pattern": r"(?i)(task completed|all tasks completed|finished)",
        "applies_to": ["stdout"],
    },
    {
        "id": "builtin.error.01",
        "event_type": "error_detected",
        "severity": "critical",
        "match_type": "contains",
        "pattern": "Error:",
        "applies_to": ["stderr"],
    },
]


class RuleEngine:
    """规则匹配引擎。"""

    def __init__(self, custom_rules: Optional[list[RuleDefinition]] = None):
        self.rules: list[RuleDefinition] = []
        self._load_rules(custom_rules)

    def _load_rules(self, custom_rules: Optional[list[RuleDefinition]]):
        # 加载内置规则
        for raw in BUILTIN_RULES:
            self.rules.append(RuleDefinition(
                id=raw["id"],
                enabled=True,
                event_type=raw["event_type"],
                severity=raw["severity"],
                match_type=raw["match_type"],
                pattern=raw["pattern"],
                applies_to=raw.get("applies_to", ["stdout", "stderr"]),
            ))

        # 加载外部规则（覆盖同 id 内置规则）
        if custom_rules:
            custom_ids = {r.id for r in custom_rules}
            self.rules = [r for r in self.rules if r.id not in custom_ids]
            self.rules.extend(custom_rules)

        # 预编译正则
        self._compiled: dict[str, re.Pattern] = {}
        for rule in self.rules:
            if rule.match_type == "regex" and rule.enabled:
                try:
                    self._compiled[rule.id] = re.compile(rule.pattern)
                except re.error as e:
                    logger.warning("规则 %s 正则编译失败: %s", rule.id, e)

        logger.info("已加载 %d 条规则", len([r for r in self.rules if r.enabled]))

    def match(self, text: str, source: str) -> list[tuple[RuleDefinition, MatchInfo]]:
        """对文本执行规则匹配，返回命中的 (规则, 匹配信息) 列表。"""
        hits = []
        for rule in self.rules:
            if not rule.enabled:
                continue
            if source not in rule.applies_to:
                continue

            hit = self._match_rule(rule, text)
            if hit:
                info = MatchInfo(
                    rule_id=rule.id,
                    pattern=rule.pattern,
                    sample_text=text[:200],
                )
                hits.append((rule, info))

        return hits

    def _match_rule(self, rule: RuleDefinition, text: str) -> bool:
        if rule.match_type == "contains":
            return rule.pattern in text

        if rule.match_type == "regex":
            compiled = self._compiled.get(rule.id)
            if compiled:
                return bool(compiled.search(text))
            return False

        if rule.match_type == "any_of":
            keywords = [kw.strip() for kw in rule.pattern.split(",")]
            return any(kw in text for kw in keywords)

        return False
