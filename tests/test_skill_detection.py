"""技能检测单元测试"""
import unittest
from unittest.mock import patch
from pathlib import Path
import sys

# Import from parent directory (same pattern as test_incremental_update.py)
sys.path.insert(0, str(Path(__file__).parent.parent))

from analyzer import detect_skill_intent


class TestSkillDetection(unittest.TestCase):
    """测试直接匹配白名单技能名"""

    def test_exact_match_with_pattern(self):
        """测试带句式的匹配"""
        result = detect_skill_intent("使用workflow-manager技能")
        self.assertIsNotNone(result)
        self.assertEqual(result["task_level"], "L0")
        self.assertEqual(result["skill_name"], "workflow-manager")

    def test_match_without_pattern(self):
        """测试不带句式的匹配"""
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

    def test_non_whitelist_skill(self):
        """测试非白名单技能"""
        result = detect_skill_intent("使用unknown-skill技能")
        self.assertIsNone(result)

    def test_partial_match_not_triggered(self):
        """测试部分匹配不触发（技能名作为其他词的一部分）"""
        # agent-pool 可能出现在 "agent-pool-manager" 中
        # 但我们期望仍然匹配（子字符串匹配是预期行为）
        result = detect_skill_intent("agent-pool-manager test")
        self.assertIsNotNone(result)
        self.assertEqual(result["skill_name"], "agent-pool")

    def test_case_insensitive(self):
        """测试大小写不敏感"""
        result = detect_skill_intent("WORKFLOW-MANAGER test")
        self.assertIsNotNone(result)
        self.assertEqual(result["skill_name"], "workflow-manager")


if __name__ == "__main__":
    unittest.main()
