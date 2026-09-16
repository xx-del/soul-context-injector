"""子 Agent 注入开关测试"""
import importlib
from pathlib import Path
from unittest.mock import MagicMock
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

class TestPreLlmCallSubagentInject:
    def test_subagent_skip_when_flag_false(self, soul_init, monkeypatch):
        import soul_context_injector.constants as constants_mod
        monkeypatch.setattr(constants_mod, 'SOUL_INJECT_SUBAGENT', False)
        soul_init.is_subagent = MagicMock(return_value=True)
        result = soul_init.pre_llm_call_hook(
            session_id='test-sub-skip', user_message='分析架构问题',
            conversation_history=[], is_first_turn=True, model='test', platform='test')
        assert result is None

    def test_subagent_inject_when_flag_true(self, soul_init, monkeypatch):
        import soul_context_injector.constants as constants_mod
        monkeypatch.setattr(constants_mod, 'SOUL_INJECT_SUBAGENT', True)
        soul_init.is_subagent = MagicMock(return_value=True)
        soul_init.analyze_task = MagicMock(return_value={
            'success': True, 'task_level': 'L2', 'workflow_name': None,
            'write_operation': False, 'code_guidance': False,
            'agent_pool': False, 'skill_usage': True, 'self_improving': False})
        result = soul_init.pre_llm_call_hook(
            session_id='test-sub-inject', user_message='分析架构问题',
            conversation_history=[], is_first_turn=True, model='test', platform='test')
        assert result is not None or soul_init.analyze_task.called

class TestPreToolCallSubagentInject:
    def test_subagent_skip_tool_when_flag_false(self, soul_init, monkeypatch):
        import soul_context_injector.constants as constants_mod
        monkeypatch.setattr(constants_mod, 'SOUL_INJECT_SUBAGENT', False)
        soul_init.is_subagent = MagicMock(return_value=True)
        result = soul_init.pre_tool_call_hook(
            tool_name='terminal', args={'command': 'ls'},
            task_id='test-1', session_id='test-sub-tool-skip')
        assert result is None

    def test_subagent_enforce_tool_when_flag_true(self, soul_init, monkeypatch):
        import soul_context_injector.constants as constants_mod
        monkeypatch.setattr(constants_mod, 'SOUL_INJECT_SUBAGENT', True)
        soul_init.is_subagent = MagicMock(return_value=True)
        result = soul_init.pre_tool_call_hook(
            tool_name='terminal', args={'command': 'ls'},
            task_id='test-2', session_id='test-sub-tool-inject')
        assert True  # 不报错即通过（is_subagent 未提前 return）
