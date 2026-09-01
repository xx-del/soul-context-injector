#!/usr/bin/env python3
"""Soul注入插件等级执行准确性测试"""
import json
import tempfile
from pathlib import Path
from unittest.mock import patch
import sys
sys.path.insert(0, str(Path(__file__).parent))
from enforcer import create_tracker, get_tracker, check_round_completion, track_skill_call, SKILL_BINDINGS

def test_skill_bindings_defined():
    assert "L2" in SKILL_BINDINGS and SKILL_BINDINGS["L2"] == ["deep-thinking"]
    assert "L3" in SKILL_BINDINGS and SKILL_BINDINGS["L3"] == ["deep-thinking", "openclaw-behavior-plan"]
    assert "L4" in SKILL_BINDINGS and SKILL_BINDINGS["L4"] == ["planning-with-files", "agent-pool"]
    print("✓ 测试1通过：SKILL_BINDINGS已正确定义")

def test_check_round_completion_empty():
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch('enforcer.TRACKING_DIR', Path(tmpdir)):
            session_id = "test_session_001"
            create_tracker(session_id, "L2", force_reset=True)
            is_complete, missing = check_round_completion(session_id, "L2")
            assert not is_complete and "deep-thinking" in missing
            print("✓ 测试2通过：空追踪器正确识别为未完成")

def test_check_round_completion_partial():
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch('enforcer.TRACKING_DIR', Path(tmpdir)):
            session_id = "test_session_002"
            create_tracker(session_id, "L3", force_reset=True)
            track_skill_call(session_id, "deep-thinking")
            is_complete, missing = check_round_completion(session_id, "L3")
            assert not is_complete and "openclaw-behavior-plan" in missing and "deep-thinking" not in missing
            print("✓ 测试3通过：部分调用正确识别缺少的技能")

def test_check_round_completion_complete():
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch('enforcer.TRACKING_DIR', Path(tmpdir)):
            session_id = "test_session_003"
            create_tracker(session_id, "L2", force_reset=True)
            track_skill_call(session_id, "deep-thinking")
            is_complete, missing = check_round_completion(session_id, "L2")
            assert is_complete and len(missing) == 0
            print("✓ 测试4通过：完全调用正确识别为已完成")

def test_l4_requires_both_skills():
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch('enforcer.TRACKING_DIR', Path(tmpdir)):
            session_id = "test_session_004"
            create_tracker(session_id, "L4", force_reset=True)
            track_skill_call(session_id, "planning-with-files")
            is_complete, missing = check_round_completion(session_id, "L4")
            assert not is_complete and "agent-pool" in missing
            print("✓ 测试5通过：L4任务正确要求两个技能")

def test_level_transition():
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch('enforcer.TRACKING_DIR', Path(tmpdir)):
            session_id = "test_session_005"
            create_tracker(session_id, "L2", force_reset=True)
            track_skill_call(session_id, "deep-thinking")
            create_tracker(session_id, "L3", force_reset=True)
            is_complete, missing = check_round_completion(session_id, "L3")
            assert not is_complete and "openclaw-behavior-plan" in missing
            print("✓ 测试6通过：等级转换正确重置技能需求")

if __name__ == "__main__":
    print("=" * 60)
    print("Soul注入插件等级执行准确性测试")
    print("=" * 60)
    test_skill_bindings_defined()
    test_check_round_completion_empty()
    test_check_round_completion_partial()
    test_check_round_completion_complete()
    test_l4_requires_both_skills()
    test_level_transition()
    print("=" * 60)
    print("所有测试通过！")
    print("=" * 60)
