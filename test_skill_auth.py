#!/usr/bin/env python3
"""测试技能验证认证 - 独立测试脚本"""
import json
import datetime
import sys
from pathlib import Path

# 测试目录
TRACKING_DIR = Path.home() / ".hermes" / "skill-tracking"
AUTH_DIR = Path.home() / ".hermes" / "execution-auth"

# 常量
SKILL_BINDINGS = {
    "L2": ["deep-thinking"],
    "L3": ["deep-thinking", "openclaw-behavior-plan"],
    "L4": ["planning-with-files", "agent-pool"],
}
REQUIRED_SKILLS_L4 = ["planning-with-files", "agent-pool"]


def create_tracker(session_id: str, task_level: str) -> Path:
    """创建技能追踪文件"""
    TRACKING_DIR.mkdir(parents=True, exist_ok=True)

    required_skills = SKILL_BINDINGS.get(task_level, [])

    tracker_data = {
        "session_id": session_id,
        "task_level": task_level,
        "created_at": datetime.datetime.now().isoformat(),
        "called_skills": [],
        "required_skills": required_skills,
    }

    tracker_file = TRACKING_DIR / f"{session_id}.json"
    tracker_file.write_text(json.dumps(tracker_data, ensure_ascii=False, indent=2))
    print(f"  创建追踪器: {tracker_file}")

    return tracker_file


def get_tracker(session_id: str):
    """获取技能追踪数据"""
    tracker_file = TRACKING_DIR / f"{session_id}.json"
    if not tracker_file.exists():
        return None
    try:
        return json.loads(tracker_file.read_text())
    except Exception:
        return None


def track_skill_call(session_id: str, skill_name: str) -> bool:
    """追踪技能调用"""
    tracker = get_tracker(session_id)
    if not tracker:
        return False

    if skill_name not in tracker["called_skills"]:
        tracker["called_skills"].append(skill_name)
        tracker_file = TRACKING_DIR / f"{session_id}.json"
        tracker_file.write_text(json.dumps(tracker, ensure_ascii=False, indent=2))
        print(f"  技能调用: {skill_name}")

    return True


def track_execution(session_id: str, execution_type: str, tool_name: str = None) -> bool:
    """追踪实际执行"""
    tracker = get_tracker(session_id)
    if not tracker:
        return False

    if "executed_by" not in tracker:
        tracker["executed_by"] = []

    if execution_type not in tracker["executed_by"]:
        tracker["executed_by"].append(execution_type)
        tracker_file = TRACKING_DIR / f"{session_id}.json"
        tracker_file.write_text(json.dumps(tracker, ensure_ascii=False, indent=2))
        print(f"  执行追踪: {execution_type}")

    return True


def has_execution_auth(session_id: str) -> bool:
    """检查是否有有效的执行认证（技能验证版本）"""
    # 方案1: 本地认证文件
    auth_file = AUTH_DIR / f"{session_id}.json"
    if auth_file.exists():
        try:
            data = json.loads(auth_file.read_text())
            if data.get("session_id") != session_id:
                return False
            expires = datetime.datetime.fromisoformat(data["expires_at"])
            if datetime.datetime.now() > expires:
                return False
            return True
        except Exception:
            pass

    # 方案2: 技能调用追踪
    tracker = get_tracker(session_id)
    if tracker:
        task_level = tracker.get("task_level")
        called = tracker.get("called_skills", [])
        executed_by = tracker.get("executed_by", [])

        # L4: 检查技能调用 + 实际执行
        if task_level == "L4":
            required = REQUIRED_SKILLS_L4
            skills_ok = all(s in called for s in required)
            exec_ok = len(executed_by) > 0
            if skills_ok and exec_ok:
                print(f"  ✓ L4 认证通过: skills={called}, execution={executed_by}")
                return True

        # L2/L3: 只检查技能调用
        elif task_level in ["L2", "L3"]:
            required = SKILL_BINDINGS.get(task_level, [])
            if all(s in called for s in required):
                print(f"  ✓ {task_level} 认证通过: skills={called}")
                return True

    return False


def cleanup_expired_trackers():
    """清理所有测试追踪文件"""
    if TRACKING_DIR.exists():
        for f in TRACKING_DIR.glob("test-*.json"):
            f.unlink()
            print(f"  清理: {f.name}")


def test_l4_auth_via_skill_tracking():
    """L4: 技能调用 + 执行追踪 → 授予认证"""
    print("\n[测试1] L4 技能验证认证")
    cleanup_expired_trackers()

    session_id = "test-l4-skill-auth"

    create_tracker(session_id, "L4")
    track_skill_call(session_id, "planning-with-files")
    track_skill_call(session_id, "agent-pool")
    track_execution(session_id, "delegate_task", "delegate_task")

    result = has_execution_auth(session_id)
    assert result == True, f"期望 True，实际 {result}"
    print("✅ 测试通过: L4 技能验证认证")


def test_l4_auth_missing_skill():
    """L4: 缺少技能 → 无认证"""
    print("\n[测试2] L4 缺少技能无认证")
    cleanup_expired_trackers()

    session_id = "test-l4-missing-skill"

    create_tracker(session_id, "L4")
    track_skill_call(session_id, "planning-with-files")
    # 没有执行

    result = has_execution_auth(session_id)
    assert result == False, f"期望 False，实际 {result}"
    print("✅ 测试通过: L4 缺少技能无认证")


def test_l3_auth_via_skill_tracking():
    """L3: 只需技能调用（无需执行追踪）"""
    print("\n[测试3] L3 技能验证认证")
    cleanup_expired_trackers()

    session_id = "test-l3-skill-auth"

    create_tracker(session_id, "L3")
    track_skill_call(session_id, "deep-thinking")
    track_skill_call(session_id, "openclaw-behavior-plan")

    result = has_execution_auth(session_id)
    assert result == True, f"期望 True，实际 {result}"
    print("✅ 测试通过: L3 技能验证认证")


def test_l2_auth_via_skill_tracking():
    """L2: 只需技能调用"""
    print("\n[测试4] L2 技能验证认证")
    cleanup_expired_trackers()

    session_id = "test-l2-skill-auth"

    create_tracker(session_id, "L2")
    track_skill_call(session_id, "deep-thinking")

    result = has_execution_auth(session_id)
    assert result == True, f"期望 True，实际 {result}"
    print("✅ 测试通过: L2 技能验证认证")


if __name__ == "__main__":
    print("=" * 50)
    print("技能验证认证测试")
    print("=" * 50)

    try:
        test_l4_auth_via_skill_tracking()
        test_l4_auth_missing_skill()
        test_l3_auth_via_skill_tracking()
        test_l2_auth_via_skill_tracking()

        print("\n" + "=" * 50)
        print("🎉 所有测试通过!")
        print("=" * 50)
    except AssertionError as e:
        print(f"\n❌ 测试失败: {e}")
        sys.exit(1)
    finally:
        cleanup_expired_trackers()
