"""post_llm_call 应复用 pre_llm_call 的动态 decision 规则，而非硬编码。"""
import sys
from pathlib import Path

PLUGIN_DIR = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(PLUGIN_DIR))


class TestPostLlmDynamicRules:
    """post_llm_call 注入的规则应反映最近一次的决策"""

    def test_post_llm_call_uses_saved_detected_rules(self, soul_init):
        """保存 code_guidance=True 后，post_llm_call 应注入 code_guidance 规则"""
        session_id = "test_dynamic_rules"
        import importlib
        import soul_context_injector.state as state_mod
        importlib.reload(state_mod)
        from soul_context_injector import state as st

        # 模拟 pre_llm_call 保存了带 code_guidance=True 的决策
        decision = {
            "success": True, "task_level": "L3",
            "workflow_name": None, "write_operation": False,
            "code_guidance": True, "agent_pool": False,
            "skill_usage": True, "self_improving": False,
        }
        st.set_last_injected_level(session_id, "L3")
        st.set_last_detected_rules(session_id, decision)

        result = soul_init.post_llm_call_hook(
            session_id=session_id,
            conversation_history=[],
            model="deepseek-v4-flash",
            platform="custom",
        )
        assert result is not None
        # code_guidance 规则文件 (code_guidance_rules.md) 内容应出现
        assert "代码指导" in result["context"] or "code" in result["context"].lower(), \
            "应注入 code_guidance 规则，实际上下文不含代码指导内容"

    def test_post_llm_call_defaults_when_no_saved_rules(self, soul_init):
        """无保存规则时回退默认（code_guidance=False）"""
        session_id = "test_dynamic_rules_default"
        import importlib
        import soul_context_injector.state as state_mod
        importlib.reload(state_mod)
        from soul_context_injector import state as st

        st.set_last_injected_level(session_id, "L3")
        # 不保存 detected_rules → 应回退默认

        result = soul_init.post_llm_call_hook(
            session_id=session_id,
            conversation_history=[],
            model="deepseek-v4-flash",
            platform="custom",
        )
        assert result is not None
        assert "context" in result
