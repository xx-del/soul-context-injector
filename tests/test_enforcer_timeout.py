"""check_execution_timeout 滑动窗口基准测试（任务1修正版）。

注意：TRACKING_DIR 必须通过 fixture/monkeypatch 切换并在测试结束后恢复，
否则会污染后续依赖 ~/.hermes/skill-tracking 的测试（曾导致
test_new_request_resets_tracker / test_pre_llm_call_w_task_creates_tracker 回归）。
"""
import datetime
from pathlib import Path

import pytest

PLUGIN_DIR = Path(__file__).parent.parent.resolve()

TRACKING_DIR = PLUGIN_DIR / ".test_tracking_timeout"
if not TRACKING_DIR.exists():
    TRACKING_DIR.mkdir(parents=True)


@pytest.fixture(autouse=True)
def _isolated_tracking_dir(monkeypatch):
    """每个测试自动切换 TRACKING_DIR，结束自动恢复，杜绝跨测试污染。"""
    from soul_context_injector import enforcer

    monkeypatch.setattr(enforcer, "TRACKING_DIR", TRACKING_DIR)
    yield


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
    (TRACKING_DIR / f"timeout-test-{session_id}.json").write_text("{}")
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
    f = TRACKING_DIR / f"{sid}.json"
    data = __import__("json").loads(f.read_text())
    data["metadata"] = None
    f.write_text(__import__("json").dumps(data))
    assert enforcer.check_execution_timeout(sid) is True


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
    (TRACKING_DIR / f"{sid}.json").write_text(__import__("json").dumps(data))

    ok, err = enforcer.check_required_skills(sid, tool_name="terminal", task_level="L2")
    assert (ok, err) == (True, None)
