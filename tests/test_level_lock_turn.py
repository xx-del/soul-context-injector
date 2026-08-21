"""Level-Lock 轮次化测试。测试同等级新请求能触发注入。"""
import tempfile
from pathlib import Path
from unittest.mock import patch
import pytest
from unittest.mock import MagicMock


@pytest.fixture
def temp_tracking_dir():
    """Use temporary directory for tracking files during tests.

    Patches TRACKING_DIR in the enforcer module that the test imports directly.
    """
    import enforcer as _enforcer
    with tempfile.TemporaryDirectory() as tmpdir:
        original = _enforcer.TRACKING_DIR
        _enforcer.TRACKING_DIR = Path(tmpdir)
        try:
            yield Path(tmpdir)
        finally:
            _enforcer.TRACKING_DIR = original


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


class TestTrackerForceReset:
    """create_tracker force_reset 应在新请求时清空 called_skills。"""

    def test_force_reset_clears_called_skills(self, temp_tracking_dir):
        """force_reset=True 时 called_skills 应被清空"""
        from enforcer import create_tracker, get_tracker, track_skill_call

        session_id = "test_force_reset"
        # 创建 tracker 并调用技能
        create_tracker(session_id, "L2")
        track_skill_call(session_id, "deep-thinking")

        tracker = get_tracker(session_id)
        assert "deep-thinking" in tracker["current"]["called_skills"]

        # force_reset 重置
        create_tracker(session_id, "L2", force_reset=True)

        tracker = get_tracker(session_id)
        assert tracker["current"]["called_skills"] == [], \
            f"force_reset 应清空 called_skills，实际: {tracker['current']['called_skills']}"

    def test_force_reset_preserves_level_and_history(self, temp_tracking_dir):
        """force_reset 应保留等级和历史"""
        from enforcer import create_tracker, get_tracker, track_skill_call

        session_id = "test_force_preserve"
        create_tracker(session_id, "L2")
        track_skill_call(session_id, "deep-thinking")

        # 等级转换 L2→L3，保留历史
        create_tracker(session_id, "L3")
        create_tracker(session_id, "L3", force_reset=True)

        tracker = get_tracker(session_id)
        assert tracker["task_level"] == "L3"
        assert len(tracker["history"]) >= 1  # L2→L3 历史保留

    def test_no_force_reset_preserves_called_skills(self, temp_tracking_dir):
        """force_reset=False（默认）时 called_skills 应保留"""
        from enforcer import create_tracker, get_tracker, track_skill_call

        session_id = "test_no_reset"
        create_tracker(session_id, "L2")
        track_skill_call(session_id, "deep-thinking")

        # 不 force_reset
        create_tracker(session_id, "L2")

        tracker = get_tracker(session_id)
        assert "deep-thinking" in tracker["current"]["called_skills"]
