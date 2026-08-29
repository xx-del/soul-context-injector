"""测试调查类消息豁免：含调查动词 + 代码/日志/配置名词的消息降级为 L1。

规则：调查动词（查看/排查/检查）+ 技术名词（代码/日志/配置）→ L1，不触发 L2 强制。
"""
import sys
from pathlib import Path
from unittest.mock import patch

PLUGIN_DIR = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(PLUGIN_DIR))


class TestInvestigationExemption:
    """调查类消息豁免：调查动词 + 技术名词 → L1"""

    def _call(self, message: str) -> dict:
        from analyzer import analyze_task
        with patch("analyzer.call_ollama_with_retry", return_value=None), \
             patch("analyzer.call_ollama", return_value=None):
            return analyze_task(message)

    # === 应降级为 L1 的调查消息 ===

    def test_check_code(self):
        """查看代码 → L1"""
        r = self._call("查看代码")
        assert r["task_level"] == "L1", f"预期L1，实际 {r['task_level']}"

    def test_check_logs(self):
        """排查日志问题 → L1"""
        r = self._call("排查日志问题")
        assert r["task_level"] == "L1", f"预期L1，实际 {r['task_level']}"

    def test_inspect_config(self):
        """检查配置 → L1"""
        r = self._call("检查配置")
        assert r["task_level"] == "L1", f"预期L1，实际 {r['task_level']}"

    def test_view_log_file(self):
        """查看日志文件 → L1"""
        r = self._call("查看日志文件")
        assert r["task_level"] == "L1", f"预期L1，实际 {r['task_level']}"

    def test_troubleshoot_system(self):
        """排查系统日志 → L1"""
        r = self._call("排查系统日志")
        assert r["task_level"] == "L1", f"预期L1，实际 {r['task_level']}"

    def test_inspect_code_with_english(self):
        """check code → L1"""
        r = self._call("check the code")
        assert r["task_level"] == "L1", f"预期L1，实际 {r['task_level']}"

    def test_investigate_log_with_english(self):
        """check logs → L1"""
        r = self._call("check logs")
        assert r["task_level"] == "L1", f"预期L1，实际 {r['task_level']}"

    # === 不应降级的场景（仅动词无技术名词） ===

    def test_check_progress_stays_l2(self):
        """检查进度（无技术名词）→ 不降级，保持 L2"""
        r = self._call("检查进度")
        # "检查"在 planning_kws 中匹配 L2，但"进度"不是技术名词，不应触发豁免
        assert r["task_level"] == "L2", f"无技术名词不应降级为L1，实际 {r['task_level']}"

    def test_only_verb_no_noun(self):
        """排查问题（'问题'不是技术名词）→ 不应降级"""
        r = self._call("排查问题")
        assert r["task_level"] != "L1", f"无技术名词不应降级为L1，实际 {r['task_level']}"

    # === 豁免不影响其他正常分类 ===

    def test_pure_greeting_unchanged(self):
        """纯问候不受影响"""
        r = self._call("你好")
        assert r["task_level"] == "L0"

    def test_fix_bug_unchanged(self):
        """修复类任务仍为 L3"""
        r = self._call("修复这个bug")
        assert r["task_level"] == "L3", f"预期L3，实际 {r['task_level']}"

    def test_create_feature_unchanged(self):
        """创建类任务仍为 L3"""
        r = self._call("创建一个新功能")
        assert r["task_level"] == "L3", f"预期L3，实际 {r['task_level']}"


class TestInvestigationExemptionIsInvestigationMessage:
    """直接测试 _is_investigation_message 辅助函数"""

    def test_has_both_verb_and_noun(self):
        from __init__ import _is_investigation_message
        assert _is_investigation_message("查看代码") is True
        assert _is_investigation_message("排查日志问题") is True
        assert _is_investigation_message("检查配置文件") is True
        assert _is_investigation_message("check the logs") is True

    def test_only_verb(self):
        from __init__ import _is_investigation_message
        assert _is_investigation_message("查看") is False
        assert _is_investigation_message("查看进度") is False
        assert _is_investigation_message("排查一下") is False

    def test_only_noun(self):
        from __init__ import _is_investigation_message
        assert _is_investigation_message("代码") is False
        assert _is_investigation_message("日志") is False

    def test_empty_string(self):
        from __init__ import _is_investigation_message
        assert _is_investigation_message("") is False
        assert _is_investigation_message("   ") is False
