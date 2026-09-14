"""HOME 漂移免疫测试。

背景：子代理隔离 HOME（export HOME=/tmp/ap_review_home*）泄漏到共享
terminal 环境。若插件路径仍用 Path.home()，gateway 在泄漏 HOME 下
加载/重载插件时，tracker/state.db/config/workflows 全部漂移到 /tmp
下孤立目录 → should_enforce / is_subagent 时有时无。

方案：所有路径统一走 constants.HERMES_HOME（优先 HERMES_HOME env，
fallback 固定绝对路径）。
"""
import importlib
import sys
from pathlib import Path

import pytest

PLUGIN_DIR = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(PLUGIN_DIR))

EXPECTED_HOME = Path("/home/kali/.hermes")


@pytest.fixture
def polluted_home(monkeypatch):
    """模拟隔离 HOME 泄漏：HOME=/tmp/ap_review_home_d，且无 HERMES_HOME env。"""
    monkeypatch.setenv("HOME", "/tmp/ap_review_home_d")
    monkeypatch.delenv("HERMES_HOME", raising=False)


def test_hermes_home_constant_fixed_under_pollution(polluted_home):
    import constants
    reloaded = importlib.reload(constants)
    assert reloaded.HERMES_HOME == EXPECTED_HOME


def test_hermes_home_env_override(polluted_home, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", "/custom/hermes")
    import constants
    reloaded = importlib.reload(constants)
    assert reloaded.HERMES_HOME == Path("/custom/hermes")


def test_tracking_dir_fixed_under_pollution(polluted_home):
    import enforcer
    reloaded = importlib.reload(enforcer)
    assert reloaded.TRACKING_DIR == EXPECTED_HOME / "skill-tracking"


def test_state_db_path_fixed_under_pollution(polluted_home):
    import subagent_detector
    reloaded = importlib.reload(subagent_detector)
    assert reloaded._STATE_DB_PATH == EXPECTED_HOME / "state.db"


def test_violations_log_fixed_under_pollution(polluted_home):
    import constants
    reloaded = importlib.reload(constants)
    assert reloaded.VIOLATIONS_LOG == EXPECTED_HOME / "logs" / "soul-violations.log"


def test_analyzer_workflows_dir_fixed_under_pollution(polluted_home):
    import analyzer
    reloaded = importlib.reload(analyzer)
    assert reloaded.WORKFLOWS_DIR == EXPECTED_HOME / "workflows"