"""测试 analyze_task() 全管线在 mock Ollama 下的边界场景

mock Ollama（call_ollama_with_retry + call_ollama 返回 None）以强制降级到本地规则，
确保测试不依赖 Ollama 服务，也不受网络影响。
覆盖 11 个边界场景：L0/L1/L2/L3/L4 各层级及多动词优先级、同意后执行排除逻辑。
"""
import sys
from pathlib import Path
from unittest.mock import patch

PLUGIN_DIR = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(PLUGIN_DIR))


class TestAnalyzeTaskCoverage:
    """mock Ollama 强制降级到本地规则，验证全管线行为"""

    def _call(self, message: str) -> dict:
        from analyzer import analyze_task
        # mock Ollama 调用，强制降级到本地规则
        with patch("analyzer.call_ollama_with_retry", return_value=None), \
             patch("analyzer.call_ollama", return_value=None):
            return analyze_task(message)

    # === L2 边界：多动词优先级 ===

    def test_l2_find_problem_in_logs(self):
        r = self._call("查看日志找出问题")
        assert r["task_level"] == "L2", f"预期L2，实际 {r['task_level']}"

    def test_l2_check_if_correct(self):
        r = self._call("我看一下这个对不对")
        assert r["task_level"] == "L2", f"预期L2，实际 {r['task_level']}"

    # === L3 边界：执行意图 ===

    def test_l3_fix_bug(self):
        r = self._call("修复bug")
        assert r["task_level"] == "L3", f"预期L3，实际 {r['task_level']}"

    def test_l3_implement_feature(self):
        r = self._call("实现一个功能")
        assert r["task_level"] == "L3", f"预期L3，实际 {r['task_level']}"

    def test_l3_english_fix(self):
        r = self._call("fix the bug in this code")
        assert r["task_level"] == "L3", f"预期L3，实际 {r['task_level']}"

    def test_l3_english_create(self):
        r = self._call("Create a new config file")
        assert r["task_level"] == "L3", f"预期L3，实际 {r['task_level']}"

    # === L4 边界 ===

    def test_l4_pure_confirm(self):
        r = self._call("确认")
        assert r["task_level"] == "L4", f"预期L4，实际 {r['task_level']}"

    def test_not_l4_confirm_then_exec(self):
        r = self._call("同意后执行")
        assert r["task_level"] != "L4", f"预期非L4，实际 {r['task_level']}"

    # === 回归保证 ===

    def test_l1_view_file(self):
        r = self._call("查看这个文件")
        assert r["task_level"] == "L1"

    def test_l0_greeting(self):
        r = self._call("你好")
        assert r["task_level"] == "L0"

    def test_l2_analysis(self):
        r = self._call("分析一下系统架构")
        assert r["task_level"] == "L2"
