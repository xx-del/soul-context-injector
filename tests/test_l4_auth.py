"""L4 认证检查测试 - 验证 agent-pool 移除后认证逻辑正确"""
import sys
from pathlib import Path
import pytest

PLUGIN_DIR = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(PLUGIN_DIR))


@pytest.fixture
def temp_tracking_dir(tmp_path, monkeypatch):
    """将 enforcer.TRACKING_DIR 隔离到临时目录。"""
    import importlib
    for mod_name in ("soul_context_injector.enforcer", "enforcer"):
        try:
            mod = importlib.import_module(mod_name)
        except Exception:
            continue
        if hasattr(mod, "TRACKING_DIR"):
            monkeypatch.setattr(mod, "TRACKING_DIR", tmp_path)
    return tmp_path


class TestL4AuthSimplified:
    """L4 认证：只需 planning-with-files 即可授予执行认证。"""

    def test_l4_auth_with_planning_only(self, temp_tracking_dir):
        """L4 调用 planning-with-files 后即获得执行认证。"""
        from enforcer import create_tracker, track_skill_call, get_tracker
        from enforcer import REQUIRED_SKILLS_L4

        session_id = "l4auth1"
        create_tracker(session_id, "L4")
        track_skill_call(session_id, "planning-with-files")

        tracker = get_tracker(session_id)
        called = tracker.get("current", {}).get("called_skills", [])
        required = REQUIRED_SKILLS_L4
        assert all(s in called for s in required)

    def test_l4_auth_without_agent_pool(self, temp_tracking_dir):
        """L4 不调用 agent-pool 也能通过技能检查。"""
        from enforcer import create_tracker, track_skill_call, get_tracker
        from enforcer import REQUIRED_SKILLS_L4

        session_id = "l4auth2"
        create_tracker(session_id, "L4")
        track_skill_call(session_id, "planning-with-files")

        tracker = get_tracker(session_id)
        called = tracker.get("current", {}).get("called_skills", [])
        required = REQUIRED_SKILLS_L4

        # REQUIRED_SKILLS_L4 只有 planning-with-files
        assert required == ["planning-with-files"]
        assert all(s in called for s in required)

    def test_required_skills_l4_definition(self):
        """REQUIRED_SKILLS_L4 仅包含 planning-with-files（agent-pool 已移除）。"""
        from enforcer import REQUIRED_SKILLS_L4
        assert REQUIRED_SKILLS_L4 == ["planning-with-files"]

    def test_l4_without_planning_fails(self, temp_tracking_dir):
        """L4 未调用 planning-with-files 时不满足技能要求。"""
        from enforcer import create_tracker, get_tracker
        from enforcer import REQUIRED_SKILLS_L4

        session_id = "l4auth3"
        create_tracker(session_id, "L4")
        # 不调用任何技能

        tracker = get_tracker(session_id)
        called = tracker.get("current", {}).get("called_skills", [])
        required = REQUIRED_SKILLS_L4
        assert not all(s in called for s in required)
