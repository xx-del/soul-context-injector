"""确认词+非新任务消息不应崩溃（回归 find_execution_plan NameError）"""
import sys
from pathlib import Path
from unittest.mock import patch

PLUGIN_DIR = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(PLUGIN_DIR))


class TestConfirmNoCrash:
    """含确认词但不是新任务的消息应安全返回 L4，而非 NameError"""

    def _call(self, message: str) -> dict:
        from analyzer import analyze_task
        # mock Ollama，强制本地降级；不再 mock find_execution_plan
        with patch("analyzer.call_ollama_with_retry", return_value=None), \
             patch("analyzer.call_ollama", return_value=None):
            return analyze_task(message)

    def test_confirm_keyword_non_new_task_returns_l4(self):
        """'这个方案没问题，就按这个来' → L4，不崩溃"""
        result = self._call("这个方案没问题，就按这个来")
        assert result["task_level"] == "L4", f"预期L4，实际 {result['task_level']}"

    def test_confirm_then_exec_still_not_l4(self):
        """'同意后执行' 仍应排除 L4（不回归）"""
        result = self._call("同意后执行")
        assert result["task_level"] != "L4", f"预期非L4，实际 {result['task_level']}"

    def test_pure_confirm_returns_l4(self):
        """'确认' 纯确认词 → L4（不回归）"""
        result = self._call("确认")
        assert result["task_level"] == "L4", f"预期L4，实际 {result['task_level']}"
