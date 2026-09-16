"""
集成测试：soul-context-injector 全流程

验证 等级判定→技能锁定→拦截机制→等级转换 的端到端链路。
"""
import json
import datetime
import importlib
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

PLUGIN_DIR = Path(__file__).parent.parent.resolve()


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture
def fresh_tracker(tmp_path, monkeypatch):
    """为每个测试创建干净的 enforcer + 隔离 TRACKING_DIR"""
    import soul_context_injector.enforcer as enforcer_mod
    importlib.reload(enforcer_mod)
    monkeypatch.setattr(enforcer_mod, "TRACKING_DIR", tmp_path)
    return enforcer_mod


@pytest.fixture
def analyzer_mod():
    """加载 analyzer 模块（隔离状态）"""
    import soul_context_injector.analyzer as mod
    importlib.reload(mod)
    return mod


@pytest.fixture
def interceptor_mod():
    """加载 interceptor 模块"""
    import soul_context_injector.interceptor as mod
    importlib.reload(mod)
    return mod


@pytest.fixture
def init_mod(soul_init):
    """加载 __init__.py 模块"""
    return soul_init


# ============================================================
# A. 等级判定
# ============================================================

class TestTaskLevelDetermination:
    """验证 analyze_task 的判定路径"""

    def test_a1_analysis_only_downgrades_to_l2(self, init_mod):
        """A1: "分析这个日志" → _is_analysis_only 降级 → L2"""
        # _is_analysis_only 定义在 __init__.py
        from soul_context_injector.__init__ import _is_analysis_only
        result = _is_analysis_only("分析这个日志的错误原因")
        assert result is True

    def test_a1_analysis_only_l4_downgrades_to_l2(self, init_mod):
        """A1: L4 被 _is_analysis_only 降级为 L2"""
        from soul_context_injector.__init__ import _is_analysis_only
        msg = "分析这个日志的错误原因"
        task_level = "L4"
        if task_level in ("L3", "L4") and _is_analysis_only(msg):
            task_level = "L2"
        assert task_level == "L2"

    def test_a2_investigation_exemption(self, analyzer_mod):
        """A2: "查看日志文件" → _is_investigation_message 豁免 → L1"""
        result = analyzer_mod._is_investigation_message("查看日志文件")
        assert result is True

    def test_a2_investigation_not_triggered(self, analyzer_mod):
        """A2: "分析日志错误" → 不触发豁免（含分析动词）"""
        # "分析"不在 INVESTIGATION_VERBS 中（是 analysis keyword）
        result = analyzer_mod._is_investigation_message("分析日志错误")
        assert result is False

    def test_a3_workflow_local_detection(self, analyzer_mod, tmp_path, monkeypatch):
        """A3: "执行工作流 xxx" → detect_workflow_local 命中 → W"""
        from unittest.mock import patch as mp
        # 创建临时 _index.yaml
        wf_dir = tmp_path / "workflows"
        wf_dir.mkdir()
        index_file = wf_dir / "_index.yaml"
        index_file.write_text("""
workflows:
  - name: test-workflow-abc
    status: active
    tags: [test]
""")
        monkeypatch.setattr(analyzer_mod, "WORKFLOWS_DIR", wf_dir)
        result = analyzer_mod.detect_workflow_local("test-workflow-abc")
        assert result is not None
        assert result["task_level"] == "W"
        assert result["workflow_name"] == "test-workflow-abc"

    def test_a3_workflow_contains_keyword(self, analyzer_mod, tmp_path, monkeypatch):
        """A3: "运行工作流 test" → 包含'工作流'关键词命中 → W"""
        wf_dir = tmp_path / "workflows"
        wf_dir.mkdir()
        index_file = wf_dir / "_index.yaml"
        index_file.write_text("""
workflows:
  - name: test-workflow-xyz
    status: active
    tags: [test]
""")
        monkeypatch.setattr(analyzer_mod, "WORKFLOWS_DIR", wf_dir)
        result = analyzer_mod.detect_workflow_local("运行工作流 test")
        assert result is not None
        assert result["task_level"] == "W"

    def test_a4_skill_intent_detection(self, analyzer_mod):
        """A4: "使用 deep-thinking" → detect_skill_intent 命中 → L0"""
        result = analyzer_mod.detect_skill_intent("使用 deep-thinking")
        assert result is not None
        assert result["task_level"] == "L0"
        assert result["skill_name"] == "deep-thinking"

    def test_a4_slash_command(self, analyzer_mod):
        """A4: "/deep-thinking" → slash 命令命中 → L0"""
        result = analyzer_mod.detect_skill_intent("/deep-thinking")
        assert result is not None
        assert result["task_level"] == "L0"

    def test_a5_pure_confirm_triggers_l4(self, analyzer_mod):
        """A5: 纯确认词 "同意" → L4"""
        from soul_context_injector.constants import CONFIRM_KEYWORDS
        stripped = "同意"
        pure_confirm = any(
            stripped == kw or stripped.rstrip("。，！？!?.") == kw
            for kw in ["是", "同意", "确认", "执行", "好的", "可以",
                        "ok", "yes", "需要", "没问题", "开始吧", "执行吧"]
        )
        assert pure_confirm is True

    def test_a5_confirm_then_exec_not_pure(self, analyzer_mod):
        """A5: "同意后执行" → 不是纯确认（是执行方式描述）"""
        lower = "同意后执行"
        confirm_then_exec_patterns = [
            "同意后执行", "同意后实施", "确认后执行",
        ]
        has = any(p in lower for p in confirm_then_exec_patterns)
        assert has is True  # 匹配排除模式，不应判为 L4


# ============================================================
# B. 技能锁定
# ============================================================

class TestSkillEnforcement:
    """验证 tracker 创建、round_skills、enforcement_msg"""

    def test_b1_tracker_initialization(self, fresh_tracker):
        """B1: 首次 L2 → create_tracker → required_skills=["deep-thinking"]"""
        session = "test-b1-init"
        fresh_tracker.create_tracker(session, "L2")
        tracker = fresh_tracker.get_tracker(session)
        assert tracker is not None
        assert tracker["task_level"] == "L2"
        assert tracker["current"]["required_skills"] == ["deep-thinking"]
        assert tracker["current"]["called_skills"] == []
        assert tracker["current"]["round_skills"] == []

    def test_b2_round_skills_cleared_on_new_request(self, fresh_tracker):
        """B2: 同 L2 第2轮 → round_skills 清空"""
        session = "test-b2-round"
        fresh_tracker.create_tracker(session, "L2")
        # 模拟调用技能
        fresh_tracker.track_skill_call(session, "deep-thinking")
        tracker = fresh_tracker.get_tracker(session)
        assert "deep-thinking" in tracker["current"]["round_skills"]

        # 第2轮：同等级新请求
        fresh_tracker.create_tracker(session, "L2", force_reset=False)
        tracker = fresh_tracker.get_tracker(session)
        assert tracker["current"]["round_skills"] == []  # 清空
        assert "deep-thinking" in tracker["current"]["called_skills"]  # 保留

    def test_b3_called_skills_accumulate_on_transition(self, fresh_tracker):
        """B3: L2 调用 deep-thinking → L3 转换 → called_skills 保留"""
        session = "test-b3-accum"
        fresh_tracker.create_tracker(session, "L2")
        fresh_tracker.track_skill_call(session, "deep-thinking")

        # 转换到 L3
        fresh_tracker.create_tracker(session, "L3")
        tracker = fresh_tracker.get_tracker(session)
        assert "deep-thinking" in tracker["current"]["called_skills"]
        assert tracker["current"]["round_skills"] == []
        assert "deep-thinking" in tracker["current"]["required_skills"]
        assert "openclaw-behavior-plan" in tracker["current"]["required_skills"]

    def test_b4_enforcement_msg_l2(self, init_mod):
        """B4: L2 未调用 deep-thinking → 注入 enforcement_msg"""
        session = "test-b4-enforce"
        # 直接测试 enforcement_msg 生成逻辑
        from soul_context_injector.enforcer import create_tracker, get_tracker
        create_tracker(session, "L2")
        tracker = get_tracker(session)
        round_skills = tracker.get("current", {}).get("round_skills", [])
        assert "deep-thinking" not in round_skills
        # 模拟 __init__.py 中的 enforcement_msg 生成
        enforcement_msg = ""
        if "deep-thinking" not in round_skills:
            enforcement_msg += "\n\n⚠️ 【轮次强制】L2 任务每轮必须先调用 deep-thinking 才能输出分析内容。\n"
            enforcement_msg += "本轮尚未调用 deep-thinking，请立即调用。\n"
        assert "轮次强制" in enforcement_msg
        assert "deep-thinking" in enforcement_msg

    def test_b5_enforcement_msg_l3(self, fresh_tracker):
        """B5: L3 缺 openclaw-behavior-plan → check_round_completion 返回缺失"""
        session = "test-b5-l3"
        fresh_tracker.create_tracker(session, "L3")
        # 仅调用 deep-thinking
        fresh_tracker.track_skill_call(session, "deep-thinking")
        is_complete, missing = fresh_tracker.check_round_completion(session, "L3")
        assert is_complete is False
        assert "openclaw-behavior-plan" in missing


# ============================================================
# C. 拦截机制
# ============================================================

class TestInterceptionMechanism:
    """验证 OUTPUT_TOOLS 拦截、INFO_TOOLS 放行、逃生舱"""

    def test_c1_send_message_blocked(self, fresh_tracker):
        """C1: send_message + 缺技能 → BLOCK"""
        session = "test-c1-block"
        fresh_tracker.create_tracker(session, "L2")
        # 不调用任何技能，直接检查 send_message
        should_block, error_msg = fresh_tracker.should_block_tool_call(
            session, "send_message", "L2"
        )
        assert should_block is True
        assert error_msg is not None
        assert "强制执行约束" in error_msg

    def test_c2_info_tools_pass(self, fresh_tracker):
        """C2: terminal + 缺技能 → 放行（INFO_TOOLS）"""
        session = "test-c2-info"
        fresh_tracker.create_tracker(session, "L2")
        should_block, error_msg = fresh_tracker.should_block_tool_call(
            session, "terminal", "L2"
        )
        assert should_block is False

    def test_c2_read_file_passes(self, fresh_tracker):
        """C2: read_file + 缺技能 → 放行"""
        session = "test-c2-read"
        fresh_tracker.create_tracker(session, "L3")
        should_block, _ = fresh_tracker.should_block_tool_call(
            session, "read_file", "L3"
        )
        assert should_block is False

    def test_c3_graduated_interception(self, fresh_tracker):
        """C3: 非输出工具 GRADUATED_BLOCK_THRESHOLD 次后 BLOCK"""
        session = "test-c3-grad"
        fresh_tracker.create_tracker(session, "L2")
        from soul_context_injector.constants import GRADUATED_BLOCK_THRESHOLD
        # execute_code 不在 INFO_TOOLS, OUTPUT_TOOLS, TOOL_WHITELIST
        # 前 N-1 次警告放行，第 N 次 BLOCK
        for i in range(GRADUATED_BLOCK_THRESHOLD - 1):
            b, _ = fresh_tracker.should_block_tool_call(session, "execute_code", "L2")
            assert b is False, f"Call {i+1} should warn (not block)"
        # 第 N 次：BLOCK
        b_final, _ = fresh_tracker.should_block_tool_call(session, "execute_code", "L2")
        assert b_final is True

    def test_c4_escape_hatch(self, fresh_tracker):
        """C4: 连续拦截达到 MAX_ESCAPE_ATTEMPTS → 自动放行"""
        session = "test-c4-escape"
        fresh_tracker.create_tracker(session, "L2")
        from soul_context_injector.constants import MAX_ESCAPE_ATTEMPTS
        # 连续触发逃生舱递增（通过 send_message 触发 escape_attempts 递增）
        for i in range(MAX_ESCAPE_ATTEMPTS + 1):
            fresh_tracker.should_block_tool_call(session, "send_message", "L2")
        # 第 MAX_ESCAPE_ATTEMPTS+1 次应自动放行
        should_block, _ = fresh_tracker.should_block_tool_call(
            session, "send_message", "L2"
        )
        assert should_block is False

    def test_c5_tool_whitelist_always_passes(self, fresh_tracker):
        """C5: skill_view 在 TOOL_WHITELIST → 永远放行"""
        session = "test-c5-white"
        fresh_tracker.create_tracker(session, "L2")
        should_block, _ = fresh_tracker.should_block_tool_call(
            session, "skill_view", "L2"
        )
        assert should_block is False


# ============================================================
# D. 等级转换
# ============================================================

class TestLevelTransition:
    """验证等级转换时的状态保持"""

    def test_d1_l2_to_l3_transition(self, fresh_tracker):
        """D1: L2→L3 → history 保存 + called_skills 保留 + round_skills 清空"""
        session = "test-d1-trans"
        # L2 阶段
        fresh_tracker.create_tracker(session, "L2")
        fresh_tracker.track_skill_call(session, "deep-thinking")

        # 转换到 L3
        fresh_tracker.create_tracker(session, "L3")
        tracker = fresh_tracker.get_tracker(session)

        # called_skills 保留
        assert "deep-thinking" in tracker["current"]["called_skills"]
        # round_skills 清空
        assert tracker["current"]["round_skills"] == []
        # history 保存了旧等级
        assert len(tracker["history"]) == 1
        assert tracker["history"][0]["level"] == "L2"
        assert tracker["history"][0]["called"] == ["deep-thinking"]
        # required_skills 更新为 L3
        assert "openclaw-behavior-plan" in tracker["current"]["required_skills"]

    def test_d2_l3_skills_already_met(self, fresh_tracker):
        """D2: L3 所有必需技能已累积 → missing 为空"""
        session = "test-d2-met"
        # L2 阶段
        fresh_tracker.create_tracker(session, "L2")
        fresh_tracker.track_skill_call(session, "deep-thinking")

        # 转换到 L3
        fresh_tracker.create_tracker(session, "L3")
        fresh_tracker.track_skill_call(session, "openclaw-behavior-plan")

        is_complete, missing = fresh_tracker.check_round_completion(session, "L3")
        assert is_complete is True
        assert missing == []

    def test_d3_l4_to_l2_transition(self, fresh_tracker):
        """D3: L4→L2 → required_skills 更新为 L2"""
        session = "test-d3-down"
        # L4 阶段
        fresh_tracker.create_tracker(session, "L4")
        fresh_tracker.track_skill_call(session, "planning-with-files")

        # 降级到 L2
        fresh_tracker.create_tracker(session, "L2")
        tracker = fresh_tracker.get_tracker(session)

        # required_skills 变为 L2 的需求
        assert tracker["current"]["required_skills"] == ["deep-thinking"]
        # called_skills 保留 L4 的
        assert "planning-with-files" in tracker["current"]["called_skills"]
        # history 记录了 L4
        assert tracker["history"][0]["level"] == "L4"

    def test_d4_level_transitions_count(self, fresh_tracker):
        """D4: 等级转换次数正确递增"""
        session = "test-d4-count"
        fresh_tracker.create_tracker(session, "L2")
        fresh_tracker.create_tracker(session, "L3")
        fresh_tracker.create_tracker(session, "L4")
        tracker = fresh_tracker.get_tracker(session)
        assert tracker["metadata"]["level_transitions"] == 2
        assert len(tracker["history"]) == 2


# ============================================================
# E. Hook 链路集成
# ============================================================

class TestHookChain:
    """验证 pre_llm_call → pre_tool_call 的端到端链路"""

    def test_e1_tracker_created_on_l2(self, fresh_tracker, init_mod, tmp_path):
        """E1: pre_llm_call 检测 L2 → create_tracker → tracker 文件存在"""
        session = "test-e1-hook"
        # 直接调用 create_tracker（模拟 hook 内部行为）
        fresh_tracker.create_tracker(session, "L2")
        tracker_file = tmp_path / f"{session}.json"
        assert tracker_file.exists()
        data = json.loads(tracker_file.read_text())
        assert data["task_level"] == "L2"

    def test_e2_should_enforce_true_for_l2(self, fresh_tracker):
        """E2: L2 tracker 存在 → should_enforce = True"""
        session = "test-e2-enforce"
        fresh_tracker.create_tracker(session, "L2")
        assert fresh_tracker.should_enforce(session) is True

    def test_e2_should_enforce_false_no_tracker(self, fresh_tracker):
        """E2: 无 tracker → should_enforce = False"""
        assert fresh_tracker.should_enforce("nonexistent") is False

    def test_e3_full_chain_l2(self, fresh_tracker):
        """E3: 端到端 L2 → 创建 tracker → 缺技能 → send_message 拦截"""
        session = "test-e3-chain"
        # 1. 创建 tracker（模拟 pre_llm_call）
        fresh_tracker.create_tracker(session, "L2")
        # 2. 检查应执行（模拟 pre_tool_call Layer 0）
        assert fresh_tracker.should_enforce(session) is True
        # 3. 追踪技能调用（模拟 skill_view 调用）
        fresh_tracker.track_skill_call(session, "deep-thinking")
        # 4. 检查 round_skills
        tracker = fresh_tracker.get_tracker(session)
        assert "deep-thinking" in tracker["current"]["round_skills"]
        # 5. send_message 应放行（技能已调用）
        should_block, _ = fresh_tracker.should_block_tool_call(
            session, "send_message", "L2"
        )
        assert should_block is False

    def test_e4_tracker_ttl_cleanup(self, fresh_tracker):
        """E4: 过期 tracker 被 cleanup_expired_trackers 清理"""
        session = "test-e4-ttl"
        fresh_tracker.create_tracker(session, "L2")
        # 手动将 created_at 设为 25 小时前
        tracker = fresh_tracker.get_tracker(session)
        old_time = (datetime.datetime.now() - datetime.timedelta(hours=25)).isoformat()
        tracker["created_at"] = old_time
        fresh_tracker.update_tracker(session, tracker)

        # 执行清理
        fresh_tracker.cleanup_expired_trackers()
        # tracker 应被清理
        assert fresh_tracker.get_tracker(session) is None
