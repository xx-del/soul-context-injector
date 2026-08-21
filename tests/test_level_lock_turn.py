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


class TestPreLLMTurnAwareInjection:
    """pre_llm_call_hook 应基于轮次判断是否跳过注入。"""

    def test_same_level_new_turn_injects(self, soul_init):
        """同等级+新轮次（conversation_history 增长）→ 应注入"""
        session_id = "test_turn_new"
        # 第1轮：空 history
        result1 = soul_init.pre_llm_call_hook(
            user_message="分析漏洞",
            session_id=session_id,
            conversation_history=[],
            is_first_turn=False,
            model="test", platform="test",
        )
        assert result1 is not None, "第1轮应注入"

        # 第2轮：history 增长（模拟新消息）
        result2 = soul_init.pre_llm_call_hook(
            user_message="分析另一个漏洞",
            session_id=session_id,
            conversation_history=[{"role": "user", "content": "分析漏洞"}, {"role": "assistant", "content": "..."}],
            is_first_turn=False,
            model="test", platform="test",
        )
        assert result2 is not None, "同等级新轮次应重新注入"

    def test_same_level_same_turn_skips(self, soul_init):
        """同等级+同轮次（conversation_history 不变）→ 应跳过"""
        session_id = "test_turn_skip"
        history = [{"role": "user", "content": "分析漏洞"}, {"role": "assistant", "content": "..."}]

        # 第1轮
        result1 = soul_init.pre_llm_call_hook(
            user_message="分析漏洞",
            session_id=session_id,
            conversation_history=history,
            is_first_turn=False,
            model="test", platform="test",
        )
        assert result1 is not None, "第1轮应注入"

        # 第2轮：相同 history（同轮次重复触发）
        result2 = soul_init.pre_llm_call_hook(
            user_message="分析漏洞",
            session_id=session_id,
            conversation_history=history,
            is_first_turn=False,
            model="test", platform="test",
        )
        assert result2 is None, "同等级同轮次应跳过"

    def test_three_messages_all_inject(self, soul_init):
        """连续3条 L2 消息，每条新轮次都应注入"""
        session_id = "test_three_msgs"
        results = []
        for i in range(3):
            history = [{"role": "user", "content": f"msg{j}"} for j in range(i)]
            result = soul_init.pre_llm_call_hook(
                user_message=f"分析任务{i}",
                session_id=session_id,
                conversation_history=history,
                is_first_turn=False,
                model="test", platform="test",
            )
            results.append(result is not None)

        assert results == [True, True, True], f"每条新消息都应注入，实际: {results}"
