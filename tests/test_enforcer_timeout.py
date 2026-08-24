"""check_execution_timeout 滑动窗口基准测试（任务1修正版）。"""
import datetime
from pathlib import Path

import pytest

PLUGIN_DIR = Path(__file__).parent.parent.resolve()

TRACKING_DIR = PLUGIN_DIR / ".test_tracking_timeout"
if not TRACKING_DIR.exists():
    TRACKING_DIR.mkdir(parents=True)


def _make_tracker(session_id, created_offset_s, last_skill_offset_s=None):
    from soul_context_injector import enforcer
    enforcer.TRACKING_DIR = TRACKING_DIR
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
    (TRACKING_DIR / f"timeout-test-{session_id}.json").write_text("{}")
    assert enforcer._write_tracker_file(f"timeout-test-{session_id}", data)
    return f"timeout-test-{session_id}"


def test_no_last_skill_uses_created_at(monkeypatch):
    sid = _make_tracker("nolast", created_offset_s=400)
    monkeypatch.setattr("soul_context_injector.enforcer.TRACKING_DIR", TRACKING_DIR)
    from soul_context_injector import enforcer
    enforcer.TRACKING_DIR = TRACKING_DIR
    # 直接读文件验证回退逻辑：无 last_skill_at → 用 created_at（400s > 120）
    import json
    tracker = json.loads((TRACKING_DIR / f"{sid}.json").read_text())
    baseline_str = (tracker.get("metadata", {}) or {}).get("last_skill_at") or tracker.get("created_at")
    elapsed = (datetime.datetime.now() - datetime.datetime.fromisoformat(baseline_str)).total_seconds()
    assert elapsed > 120
    # 通过真实函数验证
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(enforcer, "TRACKING_DIR", TRACKING_DIR)
        assert enforcer.check_execution_timeout(sid) is True


def test_recent_skill_call_resets_window():
    from soul_context_injector import enforcer
    sid = _make_tracker("recent", created_offset_s=3600, last_skill_offset_s=60)
    orig = enforcer.TRACKING_DIR
    enforcer.TRACKING_DIR = TRACKING_DIR
    try:
        assert enforcer.check_execution_timeout(sid) is False
    finally:
        enforcer.TRACKING_DIR = orig


def test_stale_skill_call_times_out_from_last_skill():
    from soul_context_injector import enforcer
    sid = _make_tracker("stale", created_offset_s=10, last_skill_offset_s=400)
    orig = enforcer.TRACKING_DIR
    enforcer.TRACKING_DIR = TRACKING_DIR
    try:
        assert enforcer.check_execution_timeout(sid) is True
    finally:
        enforcer.TRACKING_DIR = orig


def test_missing_tracker_returns_false():
    from soul_context_injector import enforcer
    orig = enforcer.TRACKING_DIR
    enforcer.TRACKING_DIR = TRACKING_DIR
    try:
        assert enforcer.check_execution_timeout("no-such-tracker-xyz") is False
    finally:
        enforcer.TRACKING_DIR = orig
