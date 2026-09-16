"""等级转换时 called_skills 清空测试 - 验证等级转换时 called_skills 被正确清空"""
import sys
from pathlib import Path
from unittest.mock import patch
import tempfile

PLUGIN_DIR = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(PLUGIN_DIR))


def test_level_transition_clears_called_skills():
    """测试等级转换时called_skills保留（累积模式），round_skills清空"""
    from enforcer import create_tracker, get_tracker, check_round_completion

    with tempfile.TemporaryDirectory() as tmpdir:
        with patch('enforcer.TRACKING_DIR', Path(tmpdir)):
            session_id = "test_session_transition"

            # 创建L2追踪器，调用deep-thinking
            create_tracker(session_id, "L2", force_reset=True)
            from enforcer import track_skill_call
            track_skill_call(session_id, "deep-thinking")

            # 验证deep-thinking已调用
            is_complete, missing = check_round_completion(session_id, "L2")
            assert is_complete, "L2任务应该已完成"

            # 转换到W等级
            create_tracker(session_id, "W", force_reset=True)

            # 验证called_skills保留（累积模式）
            tracker = get_tracker(session_id)
            called_skills = tracker.get("current", {}).get("called_skills", [])
            assert "deep-thinking" in called_skills, "累积模式下called_skills应保留"

            # 验证round_skills被清空
            round_skills = tracker.get("current", {}).get("round_skills", [])
            assert len(round_skills) == 0, "等级转换后round_skills应该被清空"

            # 验证W等级需要workflow-manager
            is_complete, missing = check_round_completion(session_id, "W")
            assert not is_complete, "W任务应该未完成"
            assert "workflow-manager" in missing, "应该缺少workflow-manager"

            print("✓ 测试通过：等级转换时called_skills被正确清空")
