"""规则引擎单元测试。"""

import sys
from pathlib import Path

# 确保项目根目录在 sys.path
ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

import pytest

from src.common.config import RuleDefinition
from src.wrapper.rule_engine import RuleEngine


@pytest.fixture
def engine():
    return RuleEngine(custom_rules=[])


@pytest.fixture
def engine_with_custom():
    custom = RuleDefinition(
        id="test.custom.01",
        enabled=True,
        event_type="task_completed",
        severity="info",
        match_type="contains",
        pattern="CUSTOM_DONE",
        applies_to=["stdout"],
    )
    return RuleEngine(custom_rules=[custom])


class TestContains:
    def test_match_found(self, engine):
        hits = engine.match("Claude wants to read a file", "stdout")
        assert len(hits) >= 1
        assert hits[0][0].event_type == "permission_blocked"

    def test_no_match(self, engine):
        hits = engine.match("normal output line", "stdout")
        # 不应命中权限相关规则
        permission_hits = [h for h in hits if h[0].event_type == "permission_blocked"]
        assert len(permission_hits) == 0


class TestRegex:
    def test_match_found(self, engine):
        hits = engine.match("Press enter to continue", "stdout")
        assert len(hits) >= 1
        assert any(h[0].event_type == "needs_input" for h in hits)

    def test_case_insensitive(self, engine):
        hits = engine.match("PRESS ENTER now", "stdout")
        assert any(h[0].event_type == "needs_input" for h in hits)

    def test_no_match(self, engine):
        hits = engine.match("just some text", "stdout")
        input_hits = [h for h in hits if h[0].event_type == "needs_input"]
        assert len(input_hits) == 0


class TestAnyOf:
    def test_match_one_keyword(self):
        rule = RuleDefinition(
            id="test.anyof",
            enabled=True,
            event_type="error_detected",
            severity="critical",
            match_type="any_of",
            pattern="error,fatal,crash",
            applies_to=["stderr"],
        )
        engine = RuleEngine(custom_rules=[rule])
        hits = engine.match("Something fatal happened", "stderr")
        assert len(hits) == 1

    def test_no_match(self):
        rule = RuleDefinition(
            id="test.anyof2",
            enabled=True,
            event_type="error_detected",
            severity="critical",
            match_type="any_of",
            pattern="error,fatal,crash",
            applies_to=["stderr"],
        )
        engine = RuleEngine(custom_rules=[rule])
        hits = engine.match("all good here", "stderr")
        assert len(hits) == 0


class TestSourceFilter:
    def test_stderr_only_rule_ignores_stdout(self):
        rule = RuleDefinition(
            id="test.stderr",
            enabled=True,
            event_type="error_detected",
            severity="critical",
            match_type="contains",
            pattern="Error:",
            applies_to=["stderr"],
        )
        engine = RuleEngine(custom_rules=[rule])
        hits = engine.match("Error: something", "stdout")
        assert len(hits) == 0

        hits = engine.match("Error: something", "stderr")
        assert len(hits) >= 1  # 内置规则 + 自定义规则都匹配


class TestCustomOverride:
    def test_custom_rule_works(self, engine_with_custom):
        hits = engine_with_custom.match("CUSTOM_DONE", "stdout")
        assert any(h[0].id == "test.custom.01" for h in hits)

    def test_builtin_still_loaded(self, engine_with_custom):
        # 内置规则仍然存在
        all_ids = [r.id for r in engine_with_custom.rules]
        assert any("builtin" in rid for rid in all_ids)


class TestDisabledRule:
    def test_disabled_rule_skipped(self):
        rule = RuleDefinition(
            id="test.disabled",
            enabled=False,
            event_type="task_completed",
            severity="info",
            match_type="contains",
            pattern="DISABLED_PATTERN",
            applies_to=["stdout"],
        )
        engine = RuleEngine(custom_rules=[rule])
        hits = engine.match("DISABLED_PATTERN", "stdout")
        assert len(hits) == 0
