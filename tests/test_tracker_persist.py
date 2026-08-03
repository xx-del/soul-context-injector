"""test_tracker_persist.py - 验证 _update_tracker_data 只走文件写入、无 persistence 死引用。

persistence.py 已删除，旧的 `from . import persistence` 分支是遗留死代码。
本测试确认：
1. enforcer.py 源码中不再引用已删除的 persistence 模块。
2. _update_tracker_data 统一走文件写入兜底。
"""

import sys
import json
import uuid
from pathlib import Path

import pytest

# 将插件目录插入 sys.path，使 `import enforcer` 直接可用（目录名含连字符，无法作为包导入）
PLUGIN_DIR = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(PLUGIN_DIR))

import enforcer  # noqa: E402


def test_no_persistence_module_reference():
    """enforcer.py 源码中不应再出现对已删除 persistence 模块的引用。"""
    source = Path(enforcer.__file__).read_text(encoding="utf-8")
    assert "from . import persistence" not in source
    assert "persistence.set_tracker" not in source


def test_update_falls_back_to_file_write(tmp_path, monkeypatch):
    """_update_tracker_data 应统一走文件写入，返回 True 且文件内容正确落盘。"""
    session_id = f"test_persist_{uuid.uuid4().hex[:8]}"

    # 将追踪目录重定向到临时目录，避免污染真实环境
    monkeypatch.setattr(enforcer, "TRACKING_DIR", tmp_path)

    # 构造一个有效 session 的 tracker
    enforcer.create_tracker(session_id, task_level="L2")

    # 调用内部更新函数，不应抛异常
    result = enforcer._update_tracker_data(session_id, {"escape_attempts": 1})
    assert result is True

    # 验证文件已写入且字段正确
    tracker_file = tmp_path / f"{session_id}.json"
    assert tracker_file.exists()
    data = json.loads(tracker_file.read_text(encoding="utf-8"))
    assert data.get("escape_attempts") == 1
    assert data.get("session_id") == session_id