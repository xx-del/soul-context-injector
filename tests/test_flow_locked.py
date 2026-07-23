"""验证 flow_locked 设置符合预期。

利用 conftest 的合成包机制加载模块。"""
import sys
from pathlib import Path
import importlib

PLUGIN_DIR = Path(__file__).parent.parent


def _load_context_builder():
    """通过合成包加载 context_builder 模块。"""
    # conftest 的 session fixture 应已创建合成包
    pkg_name = "soul_context_injector"
    if pkg_name not in sys.modules:
        import types
        pkg = types.ModuleType(pkg_name)
        pkg.__path__ = [str(PLUGIN_DIR)]
        sys.modules[pkg_name] = pkg

    # 确保依赖子模块已加载
    _ensure_submodule("soul_context_injector.constants", PLUGIN_DIR / "constants.py")
    _ensure_submodule("soul_context_injector.analyzer", PLUGIN_DIR / "analyzer.py")

    # 加载 context_builder
    spec = importlib.util.spec_from_file_location(
        "soul_context_injector.context_builder",
        PLUGIN_DIR / "context_builder.py"
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["soul_context_injector.context_builder"] = mod
    spec.loader.exec_module(mod)
    return mod


def _ensure_submodule(full_name, file_path):
    if full_name in sys.modules:
        return
    spec = importlib.util.spec_from_file_location(full_name, file_path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[full_name] = mod
    spec.loader.exec_module(mod)
    # 注册到父包
    pkg_name = full_name.rsplit(".", 1)[0]
    mod_name = full_name.rsplit(".", 1)[1]
    parent = sys.modules.get(pkg_name)
    if parent:
        setattr(parent, mod_name, mod)


def test_l2_flow_locked():
    """L2 应 flow_locked=True，强制调用 deep-thinking"""
    mod = _load_context_builder()
    info = mod.build_phase_info("L2")
    assert info["flow_locked"] is True, "L2 应强制锁定流程"


def test_l3_flow_locked():
    """L3 应 flow_locked=True（原有行为不变）"""
    mod = _load_context_builder()
    info = mod.build_phase_info("L3")
    assert info["flow_locked"] is True, "L3 应强制锁定流程"


def test_l4_flow_locked_false():
    """L4 应 flow_locked=False（允许回退 L3）"""
    mod = _load_context_builder()
    info = mod.build_phase_info("L4")
    assert info["flow_locked"] is False, "L4 应允许回退"
