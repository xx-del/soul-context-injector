"""守卫测试：豁免判定只有一处正典定义，且为精确语义。

设计意图：__init__ 精确版与 analyzer 自由组合版对宽泛组合
（检查配置文件、排查日志问题）给出相反结论，同消息两等级。
统一后本文件全部通过。

注意：不用 importlib.reload 取两边函数——reload 包 __init__
会重放模块顶层逻辑且顶层模块与合成包是两个模块对象，
行为不可靠。改为直接断言正典唯一性 + 正典语义。
"""
import sys
import types
import importlib.util
from pathlib import Path

PLUGIN_DIR = Path(__file__).resolve().parent.parent

_PKG_NAME = "soul_context_injector"
if _PKG_NAME not in sys.modules:
    _pkg = types.ModuleType(_PKG_NAME)
    _pkg.__path__ = [str(PLUGIN_DIR)]
    sys.modules[_PKG_NAME] = _pkg

from soul_context_injector.analyzer import _is_investigation_message  # noqa: E402


class TestUnifiedExemption:
    """统一后：正典唯一存在且为精确语义"""

    def test_no_local_definition_in_init(self):
        import soul_context_injector
        assert not hasattr(soul_context_injector, "_is_investigation_message")

    def test_broad_combos_not_exempted(self):
        for text in ("检查配置文件", "排查日志问题"):
            assert _is_investigation_message(text) is False

    def test_exact_pairs_exempted(self):
        for text in ("查看日志内容", "检查进程状态"):
            assert _is_investigation_message(text) is True

    def test_analysis_never_exempted(self):
        for text in ("分析代码问题", "诊断系统故障"):
            assert _is_investigation_message(text) is False
