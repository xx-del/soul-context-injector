"""验证死代码已被移除。

利用 conftest 的合成包机制加载模块。"""
import sys
from pathlib import Path

PLUGIN_DIR = Path(__file__).parent.parent


def test_is_write_operation_does_not_exist():
    """is_write_operation 应被移除"""
    # 复用 conftest 的合成包创建
    # 先确保合成包存在
    pkg_name = "soul_context_injector"
    if pkg_name not in sys.modules:
        import types
        pkg = types.ModuleType(pkg_name)
        pkg.__path__ = [str(PLUGIN_DIR)]
        sys.modules[pkg_name] = pkg

    # 加载 interceptor 模块
    import importlib
    spec = importlib.util.spec_from_file_location(
        "soul_context_injector.interceptor",
        PLUGIN_DIR / "interceptor.py"
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["soul_context_injector.interceptor"] = mod
    spec.loader.exec_module(mod)

    assert not hasattr(mod, "is_write_operation"), \
        "is_write_operation 死函数应被移除"
    assert not hasattr(mod, "is_planning_file"), \
        "is_planning_file 死函数应被移除"
