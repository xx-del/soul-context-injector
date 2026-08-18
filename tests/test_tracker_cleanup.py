"""
test_tracker_cleanup.py - Tracker 文件清理单元测试

测试 cleanup_expired_trackers() 基础功能 + 即将实现的 hook/节流功能。

验收标准：
- 测试 1-4 (基础清理): PASS
- 测试 5-9 (新功能): FAIL（功能尚未完全实现）

注意：on_session_end_hook 已在 __init__.py 中实现（line 360），
      但 plugin.yaml 尚未声明 on_session_end hook。
      _throttled_cleanup 尚未实现。
"""

import sys
import json
import datetime
import time
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

# 将插件目录插入 sys.path，使 `import enforcer` 直接可用
PLUGIN_DIR = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(PLUGIN_DIR))

import enforcer  # noqa: E402


# ========== Fixtures ==========

@pytest.fixture
def tracking_dir(tmp_path):
    """将 enforcer.TRACKING_DIR 重定向到临时目录。"""
    with patch.object(enforcer, "TRACKING_DIR", tmp_path):
        yield tmp_path


def _make_tracker(directory: Path, session_id: str, hours_ago: float):
    """创建一个模拟追踪文件，设置 created_at 为指定小时数之前。"""
    created_at = (datetime.datetime.now() - datetime.timedelta(hours=hours_ago)).isoformat()
    tracker_data = {
        "session_id": session_id,
        "task_level": "L2",
        "created_at": created_at,
        "skills_called": [],
        "history": [],
    }
    tracker_file = directory / f"{session_id}.json"
    tracker_file.write_text(json.dumps(tracker_data, ensure_ascii=False), encoding="utf-8")
    return tracker_file


# ========== 测试 1-4: 基础清理功能（预期 PASS）==========

def test_cleanup_removes_expired_trackers(tracking_dir):
    """创建 25 小时前的追踪文件，cleanup 后应被删除。"""
    expired_file = _make_tracker(tracking_dir, "expired-session", hours_ago=25)
    assert expired_file.exists(), "测试前置条件：文件应存在"

    enforcer.cleanup_expired_trackers()

    assert not expired_file.exists(), "过期追踪文件应被删除"


def test_cleanup_keeps_fresh_trackers(tracking_dir):
    """创建 1 小时前的追踪文件，cleanup 后应保留。"""
    fresh_file = _make_tracker(tracking_dir, "fresh-session", hours_ago=1)
    assert fresh_file.exists(), "测试前置条件：文件应存在"

    enforcer.cleanup_expired_trackers()

    assert fresh_file.exists(), "未过期追踪文件应保留"


def test_cleanup_handles_empty_dir(tracking_dir):
    """空目录不应报错。"""
    # tracking_dir 已是空的 tmp_path
    enforcer.cleanup_expired_trackers()  # 不应抛异常
    assert tracking_dir.exists(), "目录本身应仍存在"


def test_cleanup_handles_missing_dir(tmp_path):
    """不存在的目录不应报错。"""
    missing_dir = tmp_path / "nonexistent"
    with patch.object(enforcer, "TRACKING_DIR", missing_dir):
        enforcer.cleanup_expired_trackers()  # 不应抛异常


# ========== 测试 5: on_session_end hook 触发清理 ==========

def test_on_session_end_hook_triggers_cleanup(tracking_dir):
    """on_session_end_hook 应调用 cleanup_expired_trackers。"""
    expired_file = _make_tracker(tracking_dir, "hook-test-session", hours_ago=25)
    assert expired_file.exists()

    # 尝试导入 on_session_end_hook
    # 如果不存在，ImportError 即为预期的失败信号
    try:
        from __init__ import on_session_end_hook  # noqa: E402
    except ImportError:
        pytest.fail("on_session_end_hook 尚未在 __init__.py 中定义")

    on_session_end_hook(session_id="test")
    assert not expired_file.exists(), "on_session_end_hook 应触发清理"


# ========== 测试 6: plugin.yaml 声明 on_session_end ==========

def test_plugin_yaml_declares_on_session_end():
    """plugin.yaml 应声明 on_session_end hook。"""
    plugin_yaml_path = PLUGIN_DIR / "plugin.yaml"
    assert plugin_yaml_path.exists(), "plugin.yaml 应存在"

    with open(plugin_yaml_path, encoding="utf-8") as f:
        plugin_yaml = yaml.safe_load(f)

    hooks = plugin_yaml.get("hooks", [])
    assert "on_session_end" in hooks, (
        f"plugin.yaml hooks 应包含 on_session_end，实际: {hooks}"
    )


# ========== 测试 7: plugin.yaml hooks 与代码 register() 一致 ==========

def test_hooks_declaration_matches_code():
    """plugin.yaml hooks 应与 __init__.py register() 注册的 hooks 一致。"""
    # 读取 plugin.yaml
    plugin_yaml_path = PLUGIN_DIR / "plugin.yaml"
    with open(plugin_yaml_path, encoding="utf-8") as f:
        plugin_yaml = yaml.safe_load(f)
    yaml_hooks = set(plugin_yaml.get("hooks", []))

    # 从 __init__.py 源码提取 register() 中的 hook 名称
    init_source = (PLUGIN_DIR / "__init__.py").read_text(encoding="utf-8")
    # 匹配 ctx.register_hook("xxx", ...) 模式
    import re
    code_hooks = set(re.findall(r'register_hook\(\s*"(\w+)"', init_source))

    assert yaml_hooks == code_hooks, (
        f"plugin.yaml hooks {yaml_hooks} ≠ 代码 register() hooks {code_hooks}\n"
        f"缺少: {code_hooks - yaml_hooks}, 多余: {yaml_hooks - code_hooks}"
    )


# ========== 测试 8-9: _throttled_cleanup 节流逻辑 ==========

def test_throttled_cleanup_runs_at_most_once_per_hour(tracking_dir):
    """_throttled_cleanup 在 1 小时内最多执行一次清理。"""
    _make_tracker(tracking_dir, "throttle-1", hours_ago=25)
    _make_tracker(tracking_dir, "throttle-2", hours_ago=25)

    try:
        from __init__ import _throttled_cleanup  # noqa: E402
    except ImportError:
        pytest.fail("_throttled_cleanup 尚未在 __init__.py 中定义")

    _throttled_cleanup()
    # 第二次调用应该被节流，不执行清理
    # 即使新建一个过期文件，也不会被清理
    _make_tracker(tracking_dir, "throttle-3", hours_ago=25)

    _throttled_cleanup()

    # throttle-3 不应该被清理（因为节流跳过了第二次执行）
    assert (tracking_dir / "throttle-3.json").exists(), (
        "节流期间不应执行第二次清理"
    )


def test_throttled_cleanup_resets_after_interval(tracking_dir):
    """_throttled_cleanup 超过 1 小时间隔后应重置节流。"""
    try:
        from __init__ import _throttled_cleanup  # noqa: E402
    except ImportError:
        pytest.fail("_throttled_cleanup 尚未在 __init__.py 中定义")

    _throttled_cleanup()

    # 模拟时间推进超过 1 小时
    # 通过 monkeypatch _last_cleanup_ts 到过去
    import __init__ as soul_init
    soul_init._last_cleanup_ts = time.time() - 3601  # 1 小时 1 秒前

    _make_tracker(tracking_dir, "reset-test", hours_ago=25)
    _throttled_cleanup()

    assert not (tracking_dir / "reset-test.json").exists(), (
        "超过节流间隔后应执行清理"
    )
