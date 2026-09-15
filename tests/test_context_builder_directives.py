"""测试 rules 文件中 L2/L3 规则是否引用 4 问框架"""
import os

RULES_DIR = os.path.expanduser(
    "~/.hermes/plugins/soul-context-injector/rules"
)


def test_l2_rule_has_deep_thinking():
    """l2.md 规则文件应引用 deep-thinking"""
    path = os.path.join(RULES_DIR, "l2.md")
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    assert "deep-thinking" in content, "l2.md 未引用 deep-thinking"


def test_l3_rule_has_plan():
    """l3.md 规则文件应引用 openclaw-behavior-plan"""
    path = os.path.join(RULES_DIR, "l3.md")
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    assert "openclaw-behavior-plan" in content, "l3.md 未引用 openclaw-behavior-plan"


def test_l4_rule_has_execution():
    """l4.md 规则文件应引用 planning-with-files（agent-pool 已移除）"""
    path = os.path.join(RULES_DIR, "l4.md")
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    assert "planning-with-files" in content, "l4.md 未引用 planning-with-files"
    # agent-pool 不再是 L4 必需技能
    # 注意：不排除文档中提及 agent-pool 作为可选参考


def test_l4_rule_not强制_agent_pool():
    """l4.md 不应包含 '必须使用agent-pool' 的强制要求"""
    path = os.path.join(RULES_DIR, "l4.md")
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    assert "必须使用agent-pool" not in content, "l4.md 仍强制要求 agent-pool"


def test_w_rule_exists():
    """w.md 规则文件应引用 workflow-manager"""
    path = os.path.join(RULES_DIR, "w.md")
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    assert "workflow-manager" in content, "w.md 未引用 workflow-manager"


def test_s_rule_exists():
    """s.md 规则文件应引用 skill_view"""
    path = os.path.join(RULES_DIR, "s.md")
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    assert "skill_view" in content, "s.md 未引用 skill_view"
