"""check_execution_timeout 滑动窗口基准测试（任务1修正版）。

注意：TRACKING_DIR 必须通过 fixture/monkeypatch 切换并在测试结束后恢复，
否则会污染后续依赖 ~/.hermes/skill-tracking 的测试（曾导致
test_new_request_resets_tracker / test_pre_llm_call_w_task_creates_tracker 回归）。

TRACKING_DIR 隔离由 conftest.py 的 autouse fixture `_isolate_tracking_dir`
统一提供（tmp_path），本文件不再在仓库内创建 .test_tracking_timeout/ 目录。
"""
import datetime

import pytest

def _make_tracker(session_id, created_offset_s, last_skill_offset_s=None):
    from soul_context_injector import enforcer

    now = datetime.datetime.now().isoformat()
    data = {
        "session_id": f"timeout-test-{session_id}",
        "task_level": "L2",
        "updated_at": now,
        "current": {"required_skills": [], "called_skills": []},
        "history": [],
        "created_at": (datetime.datetime.now() - datetime.timedelta(seconds=created_offset_s)).isoformat(),
        "metadata": {},
    }
    if last_skill_offset_s is not None:
        data["metadata"]["last_skill_at"] = (
            datetime.datetime.now() - datetime.timedelta(seconds=last_skill_offset_s)
        ).isoformat()
    (enforcer.TRACKING_DIR / f"timeout-test-{session_id}.json").write_text("{}")
    assert enforcer._write_tracker_file(f"timeout-test-{session_id}", data)
    return f"timeout-test-{session_id}"


def test_no_last_skill_uses_created_at():
    from soul_context_injector import enforcer

    sid = _make_tracker("nolast", created_offset_s=400)
    # 无 last_skill_at → 回退 created_at（400s > 120s 超时阈值）
    assert enforcer.check_execution_timeout(sid) is True


def test_recent_skill_call_resets_window():
    from soul_context_injector import enforcer

    sid = _make_tracker("recent", created_offset_s=3600, last_skill_offset_s=60)
    assert enforcer.check_execution_timeout(sid) is False


def test_stale_skill_call_times_out_from_last_skill():
    from soul_context_injector import enforcer

    sid = _make_tracker("stale", created_offset_s=10, last_skill_offset_s=400)
    assert enforcer.check_execution_timeout(sid) is True


def test_corrupted_metadata_falls_back_to_created_at():
    """metadata 为 None（旧格式 tracker 迁移中间态）时不应崩溃。"""
    from soul_context_injector import enforcer

    sid = _make_tracker("corrupt", created_offset_s=400)
    f = enforcer.TRACKING_DIR / f"{sid}.json"
    data = __import__("json").loads(f.read_text())
    data["metadata"] = None
    f.write_text(__import__("json").dumps(data))
    assert enforcer.check_execution_timeout(sid) is True


def test_repeated_skill_call_renews_window():
    """重复调用同一技能也应续期 last_skill_at（修复"仅首次入列刷新"bug）。"""
    from soul_context_injector import enforcer

    sid = _make_tracker("renew", created_offset_s=290, last_skill_offset_s=290)
    current = __import__("json").loads((enforcer.TRACKING_DIR / f"{sid}.json").read_text())
    current["current"]["called_skills"] = ["deep-thinking"]
    assert enforcer._write_tracker_file(sid, current)

    # 技能已在列表中——原 bug 路径：不刷新 last_skill_at
    assert enforcer.track_skill_call(sid, "deep-thinking") is True
    # 290s < 300s 新阈值，且 last_skill_at 已续期为 now
    assert enforcer.check_execution_timeout(sid) is False


def test_timeout_check_not_short_circuit(monkeypatch):
    """check_required_skills 末尾不应再调用 check_execution_timeout（死代码已清理）。"""
    from soul_context_injector import enforcer

    def _boom(session_id):
        raise AssertionError("check_execution_timeout 不应被 check_required_skills 调用")

    monkeypatch.setattr(enforcer, "check_execution_timeout", _boom)

    sid = "timeout-test-no-short-circuit"
    now = datetime.datetime.now().isoformat()
    data = {
        "session_id": sid,
        "task_level": "L2",
        "updated_at": now,
        "current": {
            "required_skills": ["skill_view(analysis)"],
            "called_skills": ["skill_view(analysis)"],
        },
        "history": [],
        "created_at": now,
        "metadata": {},
    }
    (enforcer.TRACKING_DIR / f"{sid}.json").write_text(__import__("json").dumps(data))

    ok, err = enforcer.check_required_skills(sid, tool_name="terminal", task_level="L2")
    assert (ok, err) == (True, None)
