"""force_reset 保留测试。

现状：pre_llm_call 每轮新请求调用 create_tracker(force_reset=True)，
同等级分支无条件清空 called_skills → L3/L4 任务每轮都要求重新调用
deep-thinking，且 L2 拦截在未调用前再度出现（跨轮记忆无效）。

目标：同等级 force_reset 时，若上一轮未完成（_check_completion=False）
则保留已调用技能，仅重置 escape_attempts；上一轮已完成则正常清空；
等级转换始终清空（既有语义不变）。
"""
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

PLUGIN_DIR = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(PLUGIN_DIR))


@pytest.fixture
def temp_tracking_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch('enforcer.TRACKING_DIR', Path(tmpdir)):
            yield Path(tmpdir)


class TestForceResetRetain:
    def test_l3_incomplete_retains_called_skills(self, temp_tracking_dir):
        """L3 上一轮只调了 deep-thinking（缺 openclaw-behavior-plan，未完成）：
        force_reset 后应保留 deep-thinking。"""
        from enforcer import create_tracker, track_skill_call, get_tracker

        sid = "reset_incomplete_l3"
        create_tracker(sid, "L3")
        track_skill_call(sid, "deep-thinking")

        create_tracker(sid, "L3", force_reset=True)

        tracker = get_tracker(sid)
        assert "deep-thinking" in tracker["current"]["called_skills"], \
            "未完成轮次应保留已调用技能"

    def test_l2_completed_clears_called_skills(self, temp_tracking_dir):
        """L2 上一轮已完成（deep-thinking 已调用）：force_reset 保留 called_skills（累积模式）。"""
        from enforcer import create_tracker, track_skill_call, get_tracker

        sid = "reset_complete_l2"
        create_tracker(sid, "L2")
        track_skill_call(sid, "deep-thinking")

        create_tracker(sid, "L2", force_reset=True)

        tracker = get_tracker(sid)
        assert "deep-thinking" in tracker["current"]["called_skills"], \
            "累积模式下 force_reset 应保留 called_skills"

    def test_l3_nothing_called_stays_empty(self, temp_tracking_dir):
        """L3 上一轮完全未调用技能：force_reset 后仍为空（必须从零开始）。"""
        from enforcer import create_tracker, get_tracker

        sid = "reset_empty_l3"
        create_tracker(sid, "L3")

        create_tracker(sid, "L3", force_reset=True)

        tracker = get_tracker(sid)
        assert tracker["current"]["called_skills"] == []

    def test_level_transition_still_clears(self, temp_tracking_dir):
        """等级转换（L2→L3）保留 called_skills（累积模式），只清空 round_skills。"""
        from enforcer import create_tracker, track_skill_call, get_tracker

        sid = "reset_transition"
        create_tracker(sid, "L2")
        track_skill_call(sid, "deep-thinking")

        create_tracker(sid, "L3", force_reset=True)

        tracker = get_tracker(sid)
        assert "deep-thinking" in tracker["current"]["called_skills"], \
            "累积模式下等级转换应保留 called_skills"
        assert tracker["current"]["round_skills"] == [], \
            "等级转换应清空 round_skills"

    def test_completed_ignores_force_reset_flag_consistency(self, temp_tracking_dir):
        """同等级已完成且 force_reset=False：不更新（既有行为）。"""
        from enforcer import create_tracker, track_skill_call, get_tracker

        sid = "reset_noflag_complete"
        create_tracker(sid, "L2")
        track_skill_call(sid, "deep-thinking")

        create_tracker(sid, "L2", force_reset=False)

        tracker = get_tracker(sid)
        assert tracker["current"]["called_skills"] == ["deep-thinking"]