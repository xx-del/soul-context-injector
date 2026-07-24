"""测试 context_builder.py 中 L2/L3 directive 是否引用 4 问框架"""
import os

CONTEXT_BUILDER_PATH = os.path.expanduser(
    "~/.hermes/plugins/soul-context-injector/context_builder.py"
)


def test_l2_directive_has_four_questions():
    """L2 directive 的 '初次思考' 应引用 4 问框架"""
    with open(CONTEXT_BUILDER_PATH, 'r', encoding='utf-8') as f:
        content = f.read()
    assert "信息采集规划" in content or "①现在知道什么" in content, \
        "L2 directive 未引用 4 问框架"


def test_l3_directive_has_four_questions():
    """L3 directive 的 deep-thinking 调用应引用 4 问框架"""
    with open(CONTEXT_BUILDER_PATH, 'r', encoding='utf-8') as f:
        content = f.read()
    assert "信息采集规划" in content or "①现在知道什么" in content, \
        "L3 directive 未引用 4 问框架"


def test_l4_directive_has_state_assessment():
    """L4 directive 应有的执行前状态评估步骤"""
    with open(CONTEXT_BUILDER_PATH, 'r', encoding='utf-8') as f:
        content = f.read()
    assert "执行前状态评估" in content, "L4 directive 缺少执行前状态评估 (第零步)"
