"""调查类消息豁免精确化测试"""
import sys
from pathlib import Path
from unittest.mock import patch
import tempfile

PLUGIN_DIR = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(PLUGIN_DIR))


class TestInvestigationExemption:
    """调查类消息豁免精确化。"""

    def test_exempt_patterns_only_read_only(self):
        """只有纯读取操作豁免，分析类不豁免。"""
        from soul_context_injector.analyzer import _is_investigation_message

        # 应豁免（纯读取）
        assert _is_investigation_message("查看日志内容") == True
        assert _is_investigation_message("检查进程状态") == True

        # 不应豁免（需要分析）
        assert _is_investigation_message("分析代码问题") == False
        assert _is_investigation_message("排查配置错误") == False
        assert _is_investigation_message("诊断系统故障") == False


class TestCumulativeTracking:
    """累积追踪测试。"""

    def test_level_transition_preserves_called_skills(self):
        """等级转换时 called_skills 保留（累积模式）。"""
        from enforcer import create_tracker, track_skill_call, get_tracker

        session_id = "trans1"
        # L2 调用 deep-thinking
        create_tracker(session_id, "L2", force_reset=True)
        track_skill_call(session_id, "deep-thinking")

        # 转换到 L3
        create_tracker(session_id, "L3", force_reset=False)
        tracker = get_tracker(session_id)
        called = tracker["current"]["called_skills"]
        assert "deep-thinking" in called, f"L2→L3 转换后 called_skills 应保留 deep-thinking，实际: {called}"
        assert tracker["current"]["round_skills"] == [], "round_skills 应被清空"
