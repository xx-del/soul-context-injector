#!/usr/bin/env python
"""L4 强制执行机制简单测试"""

import sys
sys.path.insert(0, '.')

from enforcer import (
    create_tracker, get_tracker, track_execution, 
    has_executed, check_execution_timeout, MAX_ESCAPE_ATTEMPTS
)

def test_escape_mechanism():
    """测试逃生舱机制"""
    session_id = "test_escape_auto"
    create_tracker(session_id, "L4")
    
    # 模拟拦截（通过直接修改 escape_attempts）
    tracker = get_tracker(session_id)
    tracker["escape_attempts"] = 3
    from enforcer import _update_tracker_data
    _update_tracker_data(session_id, {"escape_attempts": 3})
    
    # 验证
    tracker = get_tracker(session_id)
    assert tracker["escape_attempts"] == 3, "逃生舱计数器未更新"
    print("✅ 逃生舱机制测试通过")

def test_execution_tracking():
    """测试执行追踪"""
    session_id = "test_exec_track"
    create_tracker(session_id, "L4")
    
    # 追踪执行
    track_execution(session_id, "delegate_task", "delegate_task")
    
    # 验证
    assert has_executed(session_id), "执行追踪失败"
    tracker = get_tracker(session_id)
    assert "delegate_task" in tracker["executed_by"], "executed_by 字段未更新"
    print("✅ 执行追踪测试通过")

def test_tracker_persistence():
    """测试追踪器持久化"""
    session_id = "test_persist"
    create_tracker(session_id, "L4")
    
    # 更新追踪器
    from enforcer import _update_tracker_data
    _update_tracker_data(session_id, {"custom_field": "test_value"})
    
    # 验证
    tracker = get_tracker(session_id)
    assert tracker.get("custom_field") == "test_value", "追踪器持久化失败"
    print("✅ 追踪器持久化测试通过")

if __name__ == "__main__":
    print("开始测试...")
    test_escape_mechanism()
    test_execution_tracking()
    test_tracker_persistence()
    print("\n✅ 所有测试通过！")
