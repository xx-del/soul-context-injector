"""Active skill lifecycle tests.

Tests the set-on-skill_view / clear-on-post_tool_call contract.

RED phase: post_tool_call_hook is currently `pass`, so these tests
verify the bug exists before the fix.
"""
import pytest


class TestPostToolCallClearsActiveSkill:
    """post_tool_call_hook should clear active_skill after skill_view."""

    def test_post_tool_call_clears_active_skill_after_skill_view(self, soul_init):
        """post_tool_call_hook('skill_view') clears active_skill → None"""
        soul_init.set_active_skill("deep-thinking")
        assert soul_init.get_active_skill() == "deep-thinking"

        soul_init.post_tool_call_hook(
            tool_name="skill_view",
            args={"name": "deep-thinking"},
            result={"content": "SKILL.md content..."},
            task_id="test_task",
            session_id="test_session",
        )

        # 🔴 RED: post_tool_call_hook is currently `pass`
        # active_skill should be None after skill_view completes
        assert soul_init.get_active_skill() is None, \
            "post_tool_call_hook should clear active_skill after skill_view"

    def test_post_tool_call_does_not_clear_non_skill_view(self, soul_init):
        """post_tool_call_hook('terminal') should NOT clear active_skill"""
        soul_init.set_active_skill("deep-thinking")

        soul_init.post_tool_call_hook(
            tool_name="terminal",
            args={"command": "ls -la"},
            result={"output": "file1 file2", "exit_code": 0},
            task_id="test_task",
            session_id="test_session",
        )

        # Non-skill_view tools should not touch active_skill
        assert soul_init.get_active_skill() == "deep-thinking"

    def test_post_tool_call_does_not_clear_different_skill(self, soul_init):
        """If active_skill is skill A, skill_view B should NOT clear A"""
        soul_init.set_active_skill("workflow-manager")

        soul_init.post_tool_call_hook(
            tool_name="skill_view",
            args={"name": "deep-thinking"},
            result={"content": "..."},
            task_id="test_task",
            session_id="test_session",
        )

        # active_skill is "workflow-manager", but skill_view loaded "deep-thinking"
        # post_tool_call should only clear if they match
        # 🔴 RED: might be None after fix — depends on implementation
        assert soul_init.get_active_skill() is not None, \
            "Different skill should not be cleared"


class TestPreLlmCallLayer05:
    """Layer 0.5: active_skill set + whitelist → skip injection.

    This should only skip ONE turn, not permanently.
    """

    def test_pre_llm_call_skips_when_active_skill_set(self, soul_init):
        """active_skill set → Layer 0.5 returns None (skip injection)"""
        soul_init.set_active_skill("deep-thinking")

        result = soul_init.pre_llm_call_hook(
            session_id="test_session",
            user_message="分析这个漏洞",
            conversation_history=[],
            is_first_turn=False,
            model="deepseek-v4-flash",
            platform="custom",
        )

        # Layer 0.5 should skip injection
        assert result is None, \
            "Layer 0.5 should skip injection when active_skill is whitelisted"

    def test_pre_llm_call_injects_after_active_skill_cleared(self, soul_init):
        """active_skill cleared → Layer 0.5 does not match → normal injection flow"""
        soul_init.set_active_skill(None)

        result = soul_init.pre_llm_call_hook(
            session_id="test_session",
            user_message="分析这个漏洞",
            conversation_history=[],
            is_first_turn=False,
            model="deepseek-v4-flash",
            platform="custom",
        )

        # 🔴 RED: currently returns None because Layer 0.5 blocks permanently
        # should return {"context": "[SOUL] L2 context injected"}
        assert result is not None, \
            "After active_skill cleared, pre_llm_call should inject L2 context"
        assert "context" in result, \
            "Result should contain 'context' key"


class TestActiveSkillLifecycle:
    """Full lifecycle: skill_view → set → clear → re-inject."""

    def test_full_lifecycle(self, soul_init):
        """Simulate real flow: skill_view → pre_llm_call → skill_view → pre_llm_call"""
        session_id = "test_lifecycle"
        base_kwargs = dict(
            session_id=session_id,
            conversation_history=[],
            is_first_turn=False,
            model="deepseek-v4-flash",
            platform="custom",
        )

        # Turn 1: User asks "分析漏洞"
        result1 = soul_init.pre_llm_call_hook(
            user_message="分析这个漏洞", **base_kwargs
        )
        assert result1 is not None, "Turn 1: should inject L2 context"
        assert "context" in result1

        # AI calls skill_view("deep-thinking")
        soul_init.pre_tool_call_hook(
            tool_name="skill_view",
            args={"name": "deep-thinking"},
            task_id="task1",
            session_id=session_id,
        )
        assert soul_init.get_active_skill() == "deep-thinking", \
            "pre_tool_call should set active_skill"

        # skill_view completes
        soul_init.post_tool_call_hook(
            tool_name="skill_view",
            args={"name": "deep-thinking"},
            result={"content": "..."},
            task_id="task1",
            session_id=session_id,
        )
        # 🔴 RED: should be None after fix
        assert soul_init.get_active_skill() is None, \
            "post_tool_call should clear active_skill"

        # Turn 2: AI still working on same task
        result2 = soul_init.pre_llm_call_hook(
            user_message="继续分析", **base_kwargs
        )
        # 🔴 RED: currently None because Layer 0.5 still blocks
        assert result2 is not None, \
            "Turn 2: should still inject L2 context (task not done)"
        assert "context" in result2
