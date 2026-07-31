"""技能检测单元测试"""
import unittest
from unittest.mock import patch
from pathlib import Path
import sys

# Import from parent directory (same pattern as test_incremental_update.py)
sys.path.insert(0, str(Path(__file__).parent.parent))

from analyzer import detect_skill_intent


class TestSkillDetection(unittest.TestCase):
    """测试显式技能指令匹配（排除分析/审查语境）"""

    def test_exact_match_with_pattern(self):
        """测试带句式的匹配"""
        result = detect_skill_intent("使用workflow-manager技能")
        self.assertIsNotNone(result)
        self.assertEqual(result["task_level"], "L0")
        self.assertEqual(result["skill_name"], "workflow-manager")

    def test_match_without_pattern(self):
        """测试消息以技能名开头的匹配"""
        result = detect_skill_intent("workflow-manager 处理任务")
        self.assertIsNotNone(result)
        self.assertEqual(result["task_level"], "L0")
        self.assertEqual(result["skill_name"], "workflow-manager")

    def test_match_with_spaces(self):
        """测试带空格的匹配"""
        result = detect_skill_intent("调用 workflow-manager 技能")
        self.assertIsNotNone(result)
        self.assertEqual(result["task_level"], "L0")

    def test_no_spaces(self):
        """测试无空格的匹配"""
        result = detect_skill_intent("使用workflow-manager技能")
        self.assertIsNotNone(result)
        self.assertEqual(result["task_level"], "L0")

    def test_slash_command(self):
        """测试 slash 命令格式"""
        result = detect_skill_intent("/workflow-manager 处理任务")
        self.assertIsNotNone(result)
        self.assertEqual(result["skill_name"], "workflow-manager")

    def test_non_whitelist_skill(self):
        """测试非白名单技能"""
        result = detect_skill_intent("使用unknown-skill技能")
        self.assertIsNone(result)

    def test_analysis_context_not_triggered(self):
        """分析语境不触发：'分析一下 agent-pool 的工作原理' → None"""
        result = detect_skill_intent("分析一下 agent-pool 的工作原理")
        self.assertIsNone(result)

    def test_review_context_not_triggered(self):
        """检查语境不触发：'帮我检查 workflow-manager 的问题' → None"""
        result = detect_skill_intent("帮我检查 workflow-manager 的问题")
        self.assertIsNone(result)

    def test_partial_match_not_triggered(self):
        """连字符子串不触发：'agent-pool-manager test' → None"""
        result = detect_skill_intent("agent-pool-manager test")
        self.assertIsNone(result)

    def test_case_insensitive(self):
        """测试大小写不敏感"""
        result = detect_skill_intent("WORKFLOW-MANAGER test")
        self.assertIsNotNone(result)
        self.assertEqual(result["skill_name"], "workflow-manager")


if __name__ == "__main__":
    unittest.main()
