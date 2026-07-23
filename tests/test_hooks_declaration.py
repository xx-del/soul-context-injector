"""验证 plugin.yaml hooks 声明与代码注册一致。"""
import yaml
from pathlib import Path

PLUGIN_DIR = Path(__file__).parent.parent


def test_hooks_declaration_matches_code():
    """plugin.yaml 声明的 hooks 应与 __init__.py register() 注册的一致"""
    import re
    plugin_yaml = yaml.safe_load((PLUGIN_DIR / "plugin.yaml").read_text())
    declared = set(plugin_yaml.get("hooks", []))

    init_py = (PLUGIN_DIR / "__init__.py").read_text()
    registered = set(re.findall(r'register_hook\("(\w+)"', init_py))

    assert declared == registered, \
        f"声明 {declared} vs 注册 {registered}，差异: {declared ^ registered}"
