"""等级转换时注入的测试。"""


class TestLevelTransitionInjection:
    """L2→L3→L4 等级转换应触发新规则注入。"""

    def test_same_level_skips_injection(self, soul_init):
        """同等级（L2→L2）应跳过重复注入"""
        session_id = "test_same_level"
        base_kwargs = dict(
            session_id=session_id,
            conversation_history=[],
            is_first_turn=False,
            model="deepseek-v4-flash",
            platform="custom",
        )

        # 首次应注入
        result1 = soul_init.pre_llm_call_hook(
            user_message="分析漏洞", **base_kwargs
        )
        assert result1 is not None, "首次应注入"

        # 再次调用（同等级）
        result2 = soul_init.pre_llm_call_hook(
            user_message="继续分析", **base_kwargs
        )
        assert result2 is None, "同等级应跳过注入"

    def test_level_change_triggers_new_injection(self, soul_init):
        """等级变化（L2→L4）应触发新规则注入"""
        session_id = "test_level_change"
        base_kwargs = dict(
            session_id=session_id,
            conversation_history=[],
            is_first_turn=False,
            model="deepseek-v4-flash",
            platform="custom",
        )

        # 第一轮：L2 注入
        result1 = soul_init.pre_llm_call_hook(
            user_message="分析漏洞", **base_kwargs
        )
        assert result1 is not None

        # 模拟等级变化：下次 L4 检测
        soul_init.analyze_task.return_value = {
            "success": True, "task_level": "L4",
            "workflow_name": None, "write_operation": True,
            "code_guidance": False, "agent_pool": True,
            "skill_usage": True, "self_improving": False,
        }

        result2 = soul_init.pre_llm_call_hook(
            user_message="同意", **base_kwargs
        )
        assert result2 is not None, "等级变化应注入新规则"
        assert "context" in result2

    def test_active_skill_set_does_not_block_level_change(self, soul_init):
        """active_skill=deep-thinking + 等级变化 L2→L4 → 仍应注入"""
        session_id = "test_active_skill_level_change"
        base_kwargs = dict(
            session_id=session_id,
            conversation_history=[],
            is_first_turn=False,
            model="deepseek-v4-flash",
            platform="custom",
        )

        # 设置 active_skill
        soul_init.set_active_skill("deep-thinking")

        # L4 任务
        soul_init.analyze_task.return_value = {
            "success": True, "task_level": "L4",
            "workflow_name": None, "write_operation": True,
            "code_guidance": False, "agent_pool": True,
            "skill_usage": True, "self_improving": False,
        }

        result = soul_init.pre_llm_call_hook(
            user_message="同意", **base_kwargs
        )
        assert result is not None, "active_skill 不应阻断等级变化注入"
        assert "context" in result

    def test_subagent_still_bypasses(self, soul_init):
        """子 agent 不应受等级追踪影响"""
        soul_init.is_subagent.return_value = True
        result = soul_init.pre_llm_call_hook(
            session_id="subagent",
            user_message="分析",
            conversation_history=[],
            is_first_turn=False,
            model="deepseek-v4-flash",
            platform="custom",
        )
        assert result is None, "子 agent 应放行"


class TestPostLlmCallLevelAware:
    """post_llm_call_hook 应使用最新注入等级，而非追踪器旧等级。"""

    def test_post_llm_call_uses_latest_injected_level(self, soul_init):
        """post_llm_call 使用 get_last_injected_level 而非 tracker"""
        session_id = "test_post_llm_latest_level"

        # 设置最新注入等级为 L4
        soul_init.set_last_injected_level(session_id, "L4")

        result = soul_init.post_llm_call_hook(
            session_id=session_id,
            conversation_history=[],
            model="deepseek-v4-flash",
            platform="custom",
        )

        # Should inject L4 constraint (not L2 from stale tracker)
        assert result is not None
        assert "context" in result
