"""conftest.py - 为 soul-context-injector 测试创建包上下文。

soul-context-injector 目录名包含连字符，无法直接作为 Python 包导入。
本 conftest 使用 importlib 创建合成包，使子模块间的相对导入正常工作。
"""
import sys
import types
import importlib.util
from pathlib import Path
from unittest.mock import MagicMock
import pytest

PLUGIN_DIR = Path(__file__).parent.parent.resolve()

# ========== 合成包创建 ==========

def _ensure_synthetic_package():
    """创建合成包 soul_context_injector，使其子模块相对导入正常工作。"""
    pkg_name = "soul_context_injector"
    if pkg_name in sys.modules:
        return

    pkg = types.ModuleType(pkg_name)
    pkg.__path__ = [str(PLUGIN_DIR)]
    sys.modules[pkg_name] = pkg

    # 按依赖顺序加载子模块
    _load_and_register(pkg_name, "constants", PLUGIN_DIR / "constants.py")
    _load_and_register(pkg_name, "state", PLUGIN_DIR / "state.py")


def _load_and_register(pkg_name, mod_name, file_path):
    """加载子模块并注册到 sys.modules。"""
    full_name = f"{pkg_name}.{mod_name}"
    if full_name in sys.modules:
        return

    spec = importlib.util.spec_from_file_location(full_name, file_path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[full_name] = mod
    spec.loader.exec_module(mod)

    # 将子模块设为父包的属性，使 `import pkg.sub` 能正确绑定
    parent = sys.modules.get(pkg_name)
    if parent:
        setattr(parent, mod_name, mod)


@pytest.fixture(scope="session", autouse=True)
def _synthetic_package():
    """自动创建合成包（session 级别，一次即可）。"""
    _ensure_synthetic_package()
    yield


# ========== 模块导入辅助 ==========

@pytest.fixture
def state():
    """从合成包导入 state 模块。"""
    _ensure_synthetic_package()
    import importlib
    import soul_context_injector.state
    importlib.reload(soul_context_injector.state)
    return soul_context_injector.state


@pytest.fixture
def soul_init():
    """加载 __init__.py 并用 Mock 替换 _lazy_imports 的依赖。

    __init__.py 使用 _lazy_imports() 延迟导入子模块。
    本 fixture 在调用前通过 importlib 确保合成包存在，使相对导入成功。
    """
    _ensure_synthetic_package()

    # 先确保子模块已加载
    import importlib
    import soul_context_injector.state as state_mod
    import soul_context_injector.constants as constants_mod
    importlib.reload(state_mod)  # 重置状态（_injected_levels 等）

    # 加载 __init__
    spec = importlib.util.spec_from_file_location(
        "soul_context_injector.__init__",
        PLUGIN_DIR / "__init__.py"
    )
    init_mod = importlib.util.module_from_spec(spec)
    sys.modules["soul_context_injector.__init__"] = init_mod
    spec.loader.exec_module(init_mod)

    # 覆盖 _lazy_imports 会设置的全局变量
    # 保留真正的 set_active_skill / get_active_skill（有状态，需要真实行为）
    # 覆盖 is_skill_in_whitelist 为确定行为
    init_mod.is_skill_in_whitelist = lambda name: bool(name) if name else False
    init_mod.analyze_task = MagicMock(return_value={
        "success": True,
        "task_level": "L2",
        "workflow_name": None,
        "write_operation": False,
        "code_guidance": True,
        "agent_pool": False,
        "skill_usage": True,
        "self_improving": False,
    })
    init_mod.build_context = MagicMock(return_value="[SOUL] L2 context injected")
    init_mod.is_dangerous_command = MagicMock(return_value=False)
    init_mod.log_violation = MagicMock()
    init_mod.build_error_message = MagicMock(return_value="")
    init_mod.check_workflow_completion = MagicMock(return_value=None)
    init_mod.is_subagent = MagicMock(return_value=False)
    init_mod.logger = MagicMock()

    # 重置 active_skill 状态
    state_mod.set_active_skill(None)

    yield init_mod
