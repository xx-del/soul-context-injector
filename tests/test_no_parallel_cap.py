"""守卫测试：规则文件中不得存在并行数量硬限制。"""
from pathlib import Path

PLUGIN_DIR = Path(__file__).parent.parent.resolve()
RULES_DIR = PLUGIN_DIR / "rules"
AGENT_POOL_DIR = Path("/home/kali/.hermes/skills/openclaw-imports/agent-pool")

FORBIDDEN_PATTERNS = [
    "最多 3", "最多3", "3 个并行", "3个并行",
    "超过 3 个", "超过3个", "必须分批", "max 3 parallel",
]


def _scan(path: Path) -> list:
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8")
    return [p for p in FORBIDDEN_PATTERNS if p in text]


class TestNoParallelCapInSoulRules:
    def test_agent_pool_rules_no_cap(self):
        hits = _scan(RULES_DIR / "agent_pool_rules.md")
        assert hits == [], f"agent_pool_rules.md 仍有限制表述: {hits}"

    def test_l4_rules_no_cap(self):
        hits = _scan(RULES_DIR / "l4.md")
        assert hits == [], f"l4.md 仍有限制表述: {hits}"


class TestNoParallelCapInAgentPoolSkill:
    def test_skill_md_no_cap(self):
        hits = _scan(AGENT_POOL_DIR / "SKILL.md")
        assert hits == [], f"agent-pool SKILL.md 仍有限制表述: {hits}"


class TestConstantsKeepNameForCompat:
    def test_constant_name_exists(self):
        import sys
        src = AGENT_POOL_DIR / "src"
        sys.path.insert(0, str(src))
        try:
            import constants
            assert hasattr(constants, "MAX_CONCURRENT_AGENTS")
        finally:
            if str(src) in sys.path:
                sys.path.remove(str(src))

    def test_constant_is_not_hardcoded_three(self):
        import sys
        src = AGENT_POOL_DIR / "src"
        sys.path.insert(0, str(src))
        try:
            import constants
            assert constants.MAX_CONCURRENT_AGENTS != 3, "MAX_CONCURRENT_AGENTS 仍为硬编码 3"
        finally:
            if str(src) in sys.path:
                sys.path.remove(str(src))
