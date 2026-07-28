"""测试 phase_context 注入"""
import sys
import types
import importlib
from pathlib import Path

PLUGIN_DIR = Path(__file__).parent.parent.resolve()


def _ensure_synthetic_package():
    """确保合成包 soul_context_injector 存在。"""
    pkg_name = "soul_context_injector"
    if pkg_name in sys.modules:
        return
    pkg = types.ModuleType(pkg_name)
    pkg.__path__ = [str(PLUGIN_DIR)]
    sys.modules[pkg_name] = pkg


def _ensure_submodule(full_name, file_path):
    """确保合成包子模块已加载。"""
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


def _load_context_builder():
    """通过合成包加载 context_builder 模块。"""
    _ensure_synthetic_package()
    _ensure_submodule("soul_context_injector.constants", PLUGIN_DIR / "constants.py")
    _ensure_submodule("soul_context_injector.analyzer", PLUGIN_DIR / "analyzer.py")

    spec = importlib.util.spec_from_file_location(
        "soul_context_injector.context_builder",
        PLUGIN_DIR / "context_builder.py"
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["soul_context_injector.context_builder"] = mod
    spec.loader.exec_module(mod)
    return mod


class TestPhaseContextInjection:

    def test_prompt_renders_without_error(self):
        """build_ollama_prompt 正常执行不抛异常"""
        mod = _load_context_builder()
        result = mod.build_ollama_prompt("查看文件")
        assert isinstance(result, str)
        assert len(result) > 100

    def test_user_message_placeholder_replaced(self):
        """{user_message} 占位符被替换"""
        mod = _load_context_builder()
        result = mod.build_ollama_prompt("测试消息123")
        assert "{user_message}" not in result
        assert "测试消息123" in result

    def test_phase_context_placeholder_replaced(self):
        """{phase_context} 占位符被替换（可能为空，但不能残留）"""
        mod = _load_context_builder()
        result = mod.build_ollama_prompt("查看文件")
        assert "{phase_context}" not in result
