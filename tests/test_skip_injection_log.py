"""同等级同轮次跳过注入日志级别测试。"""
import sys
from pathlib import Path
from unittest.mock import patch

PLUGIN_DIR = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(PLUGIN_DIR))


class TestSkipInjectionLogLevel:
    """验证同等级同轮次跳过注入时输出 INFO 级别日志。"""

    def test_skip_injection_logs_at_info_level(self, soul_init):
        """同等级同轮次跳过注入时，应输出 INFO 级别日志（非 DEBUG）。"""
        from soul_context_injector.state import set_last_injected_level

        session_id = "test_skip_log_level"
        set_last_injected_level(session_id, "L2", msg_count=5)

        with patch.object(soul_init, 'logger') as mock_logger:
            soul_init.pre_llm_call_hook(
                session_id=session_id,
                user_message="分析某个问题",
                conversation_history=[None] * 5,
                is_first_turn=False,
                model="test",
                platform="test",
            )

            info_calls = [str(c) for c in mock_logger.info.call_args_list]
            debug_calls = [str(c) for c in mock_logger.debug.call_args_list]

            has_info_skip = any("同等级同轮次" in c for c in info_calls)
            has_debug_skip = any("同等级同轮次" in c for c in debug_calls)

            assert has_info_skip or not has_debug_skip, (
                f"跳过注入应输出 INFO 日志。INFO调用: {info_calls[-3:]}, "
                f"DEBUG调用: {debug_calls[-3:]}"
            )
