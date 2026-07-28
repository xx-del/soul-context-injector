"""LocalRuleClient 关键词扩充与优先级修复 - 边界场景覆盖测试

验证 analyzer.py 中 LocalRuleClient._classify_task() 的各项改动：
- exec_kws 关键词扩充（L3）
- planning_kws 关键词扩充（L2）
- TASK_KEYWORDS["L2"] 追加
- 优先级顺序修复（L2 > L0 > L1 > L3）
- "同意后执行"排除逻辑
"""
import sys
from pathlib import Path

# 让 analyzer 可以作为独立模块导入（fallback 模式使用内置常量）
sys.path.insert(0, str(Path(__file__).parent.parent))
from analyzer import local_client


def _analyze(msg: str) -> str:
    """辅助函数：返回 task_level"""
    result = local_client.analyze(msg)
    return result["task_level"]


class TestL2KeywordExpansion:
    """planning_kws 扩充 + TASK_KEYWORDS["L2"] 追加 → L2"""

    def test_l2_find_problem_in_logs(self):
        """"找出"（新 planning_kws）→ L2"""
        assert _analyze("查看日志找出问题") == "L2"

    def test_l2_query_and_analyze(self):
        """"分析"（原有 planning_kws）→ L2"""
        assert _analyze("查询天气并分析") == "L2"

    def test_l2_check_if_correct(self):
        """"看一下"（新 TASK_KEYWORDS L2）→ L2"""
        assert _analyze("我看一下这个对不对") == "L2"

    def test_l3_generate_report(self):
        """"生成报告"含"生成"（新 exec_kws）→ L3"""
        assert _analyze("搜索完毕之后暂停 生成报告 再进行下一步") == "L3"

    def test_l3_how_to_implement(self):
        """"实现"（新 exec_kws）优先于"如何" → L3"""
        assert _analyze("如何实现这个功能") == "L3"

    def test_l2_what_is_this(self):
        """"what"（新 TASK_KEYWORDS L2）→ L2"""
        assert _analyze("what is this function") == "L2"


class TestL3KeywordExpansion:
    """exec_kws 扩充 → L3"""

    def test_l3_fix_bug(self):
        """"修复"（新 exec_kws）→ L3"""
        assert _analyze("修复bug") == "L3"

    def test_l3_implement_feature(self):
        """"实现"（新 exec_kws）→ L3"""
        assert _analyze("实现功能") == "L3"

    def test_l3_english_fix(self):
        """"fix"（新 exec_kws）→ L3"""
        assert _analyze("fix this issue") == "L3"

    def test_l3_create_file(self):
        """"Create"（新 exec_kws）→ L3"""
        assert _analyze("Create a new config file") == "L3"


class TestConfirmExclusion:
    """确认词排除"同意后执行"模式"""

    def test_l4_pure_confirm(self):
        """纯确认词 → L4"""
        assert _analyze("确认") == "L4"

    def test_not_l4_confirm_then_exec(self):
        """"同意后执行" → 非 L4（不被确认词逻辑捕获）"""
        assert _analyze("同意后执行") != "L4"
