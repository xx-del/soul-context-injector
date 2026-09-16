"""子 Agent 注入开关测试"""
import importlib
from pathlib import Path
import pytest

PLUGIN_DIR = Path(__file__).parent.parent.resolve()

@pytest.fixture
def fresh_constants():
    import soul_context_injector.constants as mod
    importlib.reload(mod)
    return mod

class TestSubagentInjectConfig:
    def test_config_exists_as_attribute(self, fresh_constants):
        assert hasattr(fresh_constants, 'SOUL_INJECT_SUBAGENT')
    def test_config_default_is_false(self, fresh_constants):
        assert fresh_constants.SOUL_INJECT_SUBAGENT is False
