"""test_lazy_tracker.py - 延迟 tracker 创建机制单元测试

测试 ensure_tracker() 函数：
- 缺失时自动创建
- 存在时不重复创建
- 默认等级为 L2
"""
import sys
import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# 使用 conftest.py 的合成包机制
PLUGIN_DIR = Path(__file__).parent.parent.resolve()

# 确保合成包已创建
import importlib
import types

pkg_name = "soul_context_injector"
if pkg_name not in sys.modules:
    pkg = types.ModuleType(pkg_name)
    pkg.__path__ = [str(PLUGIN_DIR)]
    sys.modules[pkg_name] = pkg

    # 加载依赖子模块
    for mod_name in ("constants", "state"):
        full_name = f"{pkg_name}.{mod_name}"
        if full_name not in sys.modules:
            spec = importlib.util.spec_from_file_location(
                full_name, PLUGIN_DIR / f"{mod_name}.py"
            )
            mod = importlib.util.module_from_spec(spec)
            sys.modules[full_name] = mod
            spec.loader.exec_module(mod)
            setattr(pkg, mod_name, mod)

# 现在可以安全导入 enforcer
import enforcer  # noqa: E402
from enforcer import ensure_tracker, get_tracker, create_tracker  # noqa: E402


@pytest.fixture
def tracking_dir(tmp_path):
    """将 enforcer.TRACKING_DIR 隔离到临时目录。"""
    with patch.object(enforcer, "TRACKING_DIR", tmp_path):
        yield tmp_path


class TestEnsureTracker:
    """ensure_tracker() 测试套件"""

    def test_creates_tracker_when_missing(self, tracking_dir):
        """验证：tracker 不存在时，ensure_tracker 应创建新 tracker"""
        session_id = "test-session-missing"

        # 确认 tracker 不存在
        assert get_tracker(session_id) is None

        # 调用 ensure_tracker
        ensure_tracker(session_id, "L2")

        # 验证 tracker 已创建
        tracker = get_tracker(session_id)
        assert tracker is not None
        assert tracker["session_id"] == session_id
        assert tracker["task_level"] == "L2"

    def test_no_op_when_tracker_exists(self, tracking_dir):
        """验证：tracker 已存在时，ensure_tracker 应跳过创建"""
        session_id = "test-session-exists"

        # 预先创建一个 tracker
        create_tracker(session_id, "L3")
        tracker_before = get_tracker(session_id)
        assert tracker_before is not None

        # 调用 ensure_tracker（不应修改已有 tracker）
        ensure_tracker(session_id, "L2")

        # 验证 tracker 未被覆盖
        tracker_after = get_tracker(session_id)
        assert tracker_after is not None
        assert tracker_after["task_level"] == "L3"

    def test_default_level_is_l2(self, tracking_dir):
        """验证：不指定 level 时，ensure_tracker 默认创建 L2 tracker"""
        session_id = "test-session-default"

        # 不传 task_level，使用默认值
        ensure_tracker(session_id)

        tracker = get_tracker(session_id)
        assert tracker is not None
        assert tracker["task_level"] == "L2"


class TestGetParentSessionId:
    def test_returns_none_for_nonexistent(self):
        from soul_context_injector.subagent_detector import get_parent_session_id
        result = get_parent_session_id('nonexistent_session_id')
        assert result is None

    def test_callable(self):
        from soul_context_injector.subagent_detector import get_parent_session_id
        assert callable(get_parent_session_id)


class TestParentTrackerInheritance:
    def test_no_parent_defaults_to_l2(self, tracking_dir):
        from soul_context_injector.enforcer import ensure_tracker, get_tracker
        session = 'orphan-session-test'
        ensure_tracker(session)
        tracker = get_tracker(session)
        assert tracker['task_level'] == 'L2'
