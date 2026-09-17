"""守卫测试：外部技能发现纪律（local_knowledge 接管，slim 摘除）。

设计意图：external_dirs 为空时系统提示零常驻，技能发现走
knowledge_search → read_file 全按需链路，规则文件必须写明该纪律，
否则弱模型想不起来查。
"""
from pathlib import Path

PLUGIN_DIR = Path(__file__).parent.parent.resolve()
RULES_DIR = PLUGIN_DIR / "rules"


def _rule_text() -> str:
    return (RULES_DIR / "skill_rules.md").read_text(encoding="utf-8")


class TestExternalDiscoveryDiscipline:
    """skill_rules.md 必须写明外部技能发现链路"""

    def test_knowledge_search_mentioned(self):
        assert "knowledge_search" in _rule_text()

    def test_read_file_on_demand_mentioned(self):
        text = _rule_text()
        assert "read_file" in text and "按需" in text

    def test_no_slim_dependency(self):
        """规则不得依赖 skill-slimmer（已摘除）"""
        text = _rule_text()
        assert "skill-slimmer" not in text
        assert "自动加载技能" not in text
