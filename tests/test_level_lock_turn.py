"""Level-Lock 轮次化测试。测试同等级新请求能触发注入。"""
import pytest
from unittest.mock import MagicMock


class TestShouldSkipInjection:
    """should_skip_injection 应同时比较 level 和 msg_count。"""

    def test_same_level_same_turn_skips(self, state):
        """同等级+同轮次 → 跳过"""
        state.set_last_injected_level("s1", "L2", msg_count=5)
        assert state.should_skip_injection("s1", "L2", 5) is True

    def test_same_level_different_turn_injects(self, state):
        """同等级+不同轮次 → 不跳过（新请求）"""
        state.set_last_injected_level("s1", "L2", msg_count=5)
        assert state.should_skip_injection("s1", "L2", 6) is False

    def test_different_level_injects(self, state):
        """不同等级 → 不跳过"""
        state.set_last_injected_level("s1", "L2", msg_count=5)
        assert state.should_skip_injection("s1", "L4", 5) is False

    def test_no_prior_injection(self, state):
        """无历史记录 → 不跳过"""
        assert state.should_skip_injection("new_session", "L2", 0) is False

    def test_get_returns_level_only(self, state):
        """get_last_injected_level 仍返回等级字符串（向后兼容）"""
        state.set_last_injected_level("s1", "L3", msg_count=10)
        assert state.get_last_injected_level("s1") == "L3"

    def test_get_returns_none_for_unknown(self, state):
        """未知 session 返回 None"""
        assert state.get_last_injected_level("unknown") is None
