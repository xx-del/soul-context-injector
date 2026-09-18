"""守卫测试：技能直调彻底跳过注入。

插件目录名 soul-context-injector 含连字符，无法作为普通 Python 包导入。
本模块自举创建一个合成包（soul_context_injector），并把插件目录设为
__path__，使 analyzer.py 内部的相对导入（from .constants / from .state）
正常工作。不依赖 conftest fixture（fixture 在收集后才执行，顶层 import 会失败），
也不依赖任何符号链接。
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

# 先注册被 analyzer 依赖的子模块（constants / state），避免相对导入失败
for _mod_name in ("constants", "state"):
    _full = f"{_PKG_NAME}.{_mod_name}"
    if _full in sys.modules:
        continue
    _spec = importlib.util.spec_from_file_location(_full, PLUGIN_DIR / f"{_mod_name}.py")
    _mod = importlib.util.module_from_spec(_spec)
    sys.modules[_full] = _mod
    _spec.loader.exec_module(_mod)
    setattr(sys.modules[_PKG_NAME], _mod_name, _mod)

from soul_context_injector.analyzer import should_skip_for_skill  # noqa: E402


"""守卫测试：技能直调彻底跳过注入。"""


class TestSkillDirectSkip:
    def test_l0_with_skill_name_skips(self):
        assert should_skip_for_skill({"task_level": "L0", "skill_name": "agent-pool"}) is True

    def test_l0_without_skill_name_no_skip(self):
        assert should_skip_for_skill({"task_level": "L0"}) is False

    def test_l2_never_skips(self):
        assert should_skip_for_skill({"task_level": "L2"}) is False
