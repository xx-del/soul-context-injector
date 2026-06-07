"""
Integration tests for enforcer incremental update mechanism.

Tests:
- Level transitions (L2 → L3 → L4)
- Skill history preservation
- Concurrent safety
- Migration from old format
"""

import json
import os
import tempfile
import threading
import time
import pytest
from pathlib import Path
from unittest.mock import patch

# Import from parent directory
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from enforcer import (
    create_tracker,
    get_tracker,
    track_skill_call,
    check_required_skills,
    update_tracker,
    migrate_tracker,
    TRACKING_DIR,
)


@pytest.fixture
def temp_tracking_dir():
    """Use temporary directory for tracking files during tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch('enforcer.TRACKING_DIR', Path(tmpdir)):
            yield Path(tmpdir)


class TestLevelTransition:
    """测试任务等级转换"""

    def test_l2_to_l3_transition(self, temp_tracking_dir):
        """L2 → L3 转换应保留 deep-thinking 技能"""
        session_id = "test_l2_to_l3"

        # Turn 1: L2 任务
        create_tracker(session_id, "L2")
        track_skill_call(session_id, "deep-thinking")

        # 验证 L2 完成
        all_called, _ = check_required_skills(session_id)
        assert all_called == True

        # Turn 2: L3 任务（等级转换）
        create_tracker(session_id, "L3")

        # 验证 deep-thinking 保留
        tracker = get_tracker(session_id)
        assert "deep-thinking" in tracker["current"]["called_skills"]

        # 验证只需调用 openclaw-behavior-plan
        all_called, error = check_required_skills(session_id)
        assert all_called == False
        assert "openclaw-behavior-plan" in error

        # 调用 openclaw-behavior-plan
        track_skill_call(session_id, "openclaw-behavior-plan")

        # 验证 L3 完成
        all_called, _ = check_required_skills(session_id)
        assert all_called == True

    def test_l3_to_l2_downgrade(self, temp_tracking_dir):
        """L3 → L2 降级应保留已调用技能"""
        session_id = "test_l3_to_l2"

        # Turn 1: L3 任务
        create_tracker(session_id, "L3")
        track_skill_call(session_id, "deep-thinking")
        track_skill_call(session_id, "openclaw-behavior-plan")

        # Turn 2: L2 任务（降级）
        create_tracker(session_id, "L2")

        # 验证：已调用技能保留
        tracker = get_tracker(session_id)
        assert "deep-thinking" in tracker["current"]["called_skills"]
        assert "openclaw-behavior-plan" in tracker["current"]["called_skills"]

        # 验证：L2 已完成（deep-thinking 已调用）
        all_called, _ = check_required_skills(session_id)
        assert all_called == True

    def test_history_limit(self, temp_tracking_dir):
        """历史最多保留 10 条"""
        session_id = "test_history_limit"

        # 连续转换 15 次
        for i in range(15):
            level = "L2" if i % 2 == 0 else "L3"
            create_tracker(session_id, level)

        tracker = get_tracker(session_id)

        # 验证：历史最多 10 条
        assert len(tracker["history"]) <= 10


class TestConcurrency:
    """测试并发安全"""

    def test_concurrent_write(self, temp_tracking_dir):
        """并发写入应安全"""
        session_id = "test_concurrent"
        results = []

        def write_tracker(level):
            try:
                create_tracker(session_id, level)
                results.append(True)
            except Exception as e:
                results.append(False)

        # 两个线程同时写入
        t1 = threading.Thread(target=write_tracker, args=("L2",))
        t2 = threading.Thread(target=write_tracker, args=("L3",))

        t1.start()
        t2.start()

        t1.join()
        t2.join()

        # 验证：至少一个成功
        assert any(results)

        # 验证：追踪文件完整
        tracker = get_tracker(session_id)
        assert tracker is not None
        assert "task_level" in tracker


class TestMigration:
    """测试旧格式迁移"""

    def test_migrate_old_format(self, temp_tracking_dir):
        """旧格式追踪器应自动迁移"""
        session_id = "test_migrate"

        # 创建旧格式追踪文件
        old_tracker = {
            "session_id": session_id,
            "task_level": "L2",
            "created_at": "2026-06-07T10:00:00",
            "called_skills": ["deep-thinking"],
            "required_skills": ["deep-thinking"]
        }

        tracker_file = temp_tracking_dir / f"{session_id}.json"
        tracker_file.write_text(json.dumps(old_tracker))

        # 读取（应自动迁移）
        tracker = get_tracker(session_id)

        # 验证：新格式
        assert "current" in tracker
        assert "history" in tracker
        assert "metadata" in tracker
        assert "deep-thinking" in tracker["current"]["called_skills"]

    def test_migrate_tracker_function(self):
        """migrate_tracker 函数应正确转换"""
        old_tracker = {
            "session_id": "test",
            "task_level": "L3",
            "created_at": "2026-06-07T10:00:00",
            "called_skills": ["deep-thinking", "openclaw-behavior-plan"],
            "required_skills": ["deep-thinking", "openclaw-behavior-plan"]
        }

        new_tracker = migrate_tracker(old_tracker)

        assert new_tracker["session_id"] == "test"
        assert new_tracker["task_level"] == "L3"
        assert new_tracker["current"]["called_skills"] == ["deep-thinking", "openclaw-behavior-plan"]
        assert new_tracker["metadata"]["total_calls"] == 2


class TestIntegration:
    """集成测试"""

    def test_full_workflow(self, temp_tracking_dir):
        """完整工作流测试：L2 → L3 → L4"""
        session_id = "test_full_workflow"

        # Phase 1: 分析问题（L2）
        create_tracker(session_id, "L2")
        track_skill_call(session_id, "deep-thinking")

        all_called, _ = check_required_skills(session_id)
        assert all_called == True

        # Phase 2: 生成方案（L3）
        create_tracker(session_id, "L3")

        # deep-thinking 已调用，只需 openclaw-behavior-plan
        track_skill_call(session_id, "openclaw-behavior-plan")

        all_called, _ = check_required_skills(session_id)
        assert all_called == True

        # Phase 3: 执行方案（L4）
        create_tracker(session_id, "L4")

        # deep-thinking 已调用，需 planning-with-files, agent-pool
        track_skill_call(session_id, "planning-with-files")
        track_skill_call(session_id, "agent-pool")

        # L4 还需要实际执行
        all_called, error = check_required_skills(session_id)
        assert all_called == False  # 缺少 executed_by
        assert "未执行实际任务" in error

        # 验证历史
        tracker = get_tracker(session_id)
        assert len(tracker["history"]) == 2  # L2→L3, L3→L4
        assert tracker["history"][0]["level"] == "L2"
        assert tracker["history"][1]["level"] == "L3"
