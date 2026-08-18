# Tracker 文件堆积清理 - TDD 实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 修复 soul-context-injector 插件追踪文件只增不减的问题（1467 个文件，6MB），通过接入 `on_session_end` hook + 节流兜底实现自动清理。

**架构：** 双保险机制 — `on_session_end` 为主清理时机（session 结束时触发），`pre_llm_call` 节流兜底（每小时最多1次，防止 session_end 未触发）。现有 `cleanup_expired_trackers()` 函数逻辑正确，只需接入 hook 生命周期。

**技术栈：** Python, pytest, fcntl, Hermes Plugin Hook System

---

## 文件结构

| 文件 | 操作 | 职责 |
|------|------|------|
| `tests/test_tracker_cleanup.py` | 创建 | 清理逻辑的单元测试 |
| `__init__.py` | 修改 | 注册 on_session_end hook + 节流兜底 |
| `plugin.yaml` | 修改 | hooks 声明添加 on_session_end |
| `~/.hermes/skill-tracking/*.json` | 运行时清理 | 删除过期追踪文件 |

---

### 任务 1：验证 `cleanup_expired_trackers()` 基础功能

**文件：**
- 测试：`tests/test_tracker_cleanup.py`（新建）
- 被测：`enforcer.py:331`（已有，不修改）

- [ ] **步骤 1：编写失败的测试**

```python
"""tracker 文件清理机制测试"""
import json
import time
import pytest
from pathlib import Path
from unittest.mock import patch

PLUGIN_DIR = Path(__file__).parent.parent


@pytest.fixture
def tracking_dir(tmp_path):
    """使用临时目录替代真实 skill-tracking 目录"""
    with patch("enforcer.TRACKING_DIR", tmp_path):
        yield tmp_path


def _create_tracker_file(directory: Path, session_id: str, created_at: str):
    """辅助函数：创建一个追踪文件"""
    data = {
        "session_id": session_id,
        "task_level": "L2",
        "created_at": created_at,
        "updated_at": created_at,
        "current": {"required_skills": ["deep-thinking"], "called_skills": []},
        "history": [],
        "metadata": {"total_calls": 0, "level_transitions": 0, "last_skill_at": None},
    }
    fpath = directory / f"{session_id}.json"
    fpath.write_text(json.dumps(data, ensure_ascii=False))
    return fpath


def test_cleanup_removes_expired_trackers(tracking_dir):
    """过期追踪文件应被删除"""
    from enforcer import cleanup_expired_trackers

    # 创建一个25小时前的文件（超过24小时TTL）
    old_time = (time.time() - 25 * 3600)
    from datetime import datetime
    old_dt = datetime.fromtimestamp(old_time).isoformat()
    _create_tracker_file(tracking_dir, "old_session", old_dt)

    assert len(list(tracking_dir.glob("*.json"))) == 1

    cleanup_expired_trackers()

    assert len(list(tracking_dir.glob("*.json"))) == 0


def test_cleanup_keeps_fresh_trackers(tracking_dir):
    """未过期的追踪文件应被保留"""
    from enforcer import cleanup_expired_trackers

    # 创建一个1小时前的文件（未超过24小时TTL）
    from datetime import datetime
    fresh_dt = datetime.fromtimestamp(time.time() - 3600).isoformat()
    _create_tracker_file(tracking_dir, "fresh_session", fresh_dt)

    cleanup_expired_trackers()

    assert len(list(tracking_dir.glob("*.json"))) == 1


def test_cleanup_handles_empty_dir(tracking_dir):
    """空目录不应报错"""
    from enforcer import cleanup_expired_trackers
    cleanup_expired_trackers()  # 不抛异常


def test_cleanup_handles_missing_dir(tmp_path):
    """不存在的目录不应报错"""
    from enforcer import cleanup_expired_trackers
    fake_dir = tmp_path / "nonexistent"
    with patch("enforcer.TRACKING_DIR", fake_dir):
        cleanup_expired_trackers()  # 不抛异常
```

- [ ] **步骤 2：运行测试验证失败**

```bash
cd /home/kali/.hermes/plugins/soul-context-injector && python3 -m pytest tests/test_tracker_cleanup.py -v --tb=short 2>&1
```

预期：PASS（因为 `cleanup_expired_trackers()` 已存在且逻辑正确）

说明：此任务验证现有函数行为，确认它是可靠的基础设施。

- [ ] **步骤 3：确认测试通过**

4 个测试全部 PASS，确认清理函数基础功能正常。

---

### 任务 2：验证 `on_session_end` hook 能触发清理

**文件：**
- 测试：`tests/test_tracker_cleanup.py`（追加）
- 被测：`__init__.py`（待修改）

- [ ] **步骤 1：编写失败的测试**

```python
def test_on_session_end_hook_triggers_cleanup(tracking_dir):
    """on_session_end hook 应调用 cleanup_expired_trackers"""
    from datetime import datetime

    # 创建过期文件
    old_dt = datetime.fromtimestamp(time.time() - 25 * 3600).isoformat()
    _create_tracker_file(tracking_dir, "expired_session", old_dt)
    assert len(list(tracking_dir.glob("*.json"))) == 1

    # 导入 hook 函数
    from importlib import import_module
    init = import_module("soul-context-injector.__init__"
                         if False else "__init__")
    # 直接测试 hook 函数
    from __init__ import on_session_end_hook
    on_session_end_hook(session_id="test")

    assert len(list(tracking_dir.glob("*.json"))) == 0


def test_plugin_yaml_declares_on_session_end():
    """plugin.yaml 应声明 on_session_end hook"""
    import yaml
    plugin_yaml = yaml.safe_load((PLUGIN_DIR / "plugin.yaml").read_text())
    assert "on_session_end" in plugin_yaml.get("hooks", [])


def test_hooks_declaration_matches_code():
    """plugin.yaml hooks 应与 __init__.py register() 一致"""
    import re
    plugin_yaml = yaml.safe_load((PLUGIN_DIR / "plugin.yaml").read_text())
    declared = set(plugin_yaml.get("hooks", []))
    init_py = (PLUGIN_DIR / "__init__.py").read_text()
    registered = set(re.findall(r'register_hook\("(\w+)"', init_py))
    assert declared == registered, \
        f"声明 {declared} vs 注册 {registered}，差异: {declared ^ registered}"
```

- [ ] **步骤 2：运行测试验证失败**

```bash
cd /home/kali/.hermes/plugins/soul-context-injector && python3 -m pytest tests/test_tracker_cleanup.py::test_on_session_end_hook_triggers_cleanup tests/test_tracker_cleanup.py::test_plugin_yaml_declares_on_session_end tests/test_tracker_cleanup.py::test_hooks_declaration_matches_code -v --tb=short 2>&1
```

预期：FAIL — `on_session_end_hook` 不存在，plugin.yaml 缺少 `on_session_end` 声明。

---

### 任务 3：实现 `on_session_end` hook

**文件：**
- 修改：`__init__.py:360-366`（register 函数）
- 修改：`plugin.yaml:23-27`（hooks 声明）

- [ ] **步骤 1：在 `__init__.py` 添加 hook 函数**

在 `post_llm_call_hook` 函数之后、`register` 函数之前，添加：

```python
def on_session_end_hook(**kwargs):
    """Session 结束时清理过期追踪文件
    
    主清理时机：session 结束时自然触发，
    避免 skill-tracking/ 目录文件无限堆积。
    """
    try:
        from .enforcer import cleanup_expired_trackers
        cleanup_expired_trackers()
    except Exception as e:
        logger.error(f"[SOUL] session 结束清理失败: {e}")
```

- [ ] **步骤 2：在 `register()` 中注册 hook**

修改 `register` 函数，追加一行：

```python
def register(ctx):
    """插件注册入口"""
    ctx.register_hook("pre_llm_call", pre_llm_call_hook)
    ctx.register_hook("pre_tool_call", pre_tool_call_hook)
    ctx.register_hook("post_tool_call", post_tool_call_hook)
    ctx.register_hook("post_llm_call", post_llm_call_hook)
    ctx.register_hook("on_session_end", on_session_end_hook)  # v5.11.1: session 结束清理
    logger.info("[soul-context-injector] 插件已加载 v5.11.1")
```

- [ ] **步骤 3：更新 `plugin.yaml` hooks 声明**

```yaml
hooks:
  - pre_llm_call    # LLM 调用前注入上下文
  - pre_tool_call   # 工具调用前拦截危险命令
  - post_tool_call  # 工具调用后清理
  - post_llm_call   # LLM 调用后持续注入约束
  - on_session_end  # Session 结束时清理过期追踪文件
```

- [ ] **步骤 4：运行测试验证通过**

```bash
cd /home/kali/.hermes/plugins/soul-context-injector && python3 -m pytest tests/test_tracker_cleanup.py -v --tb=short 2>&1
```

预期：全部 PASS（包括 hooks 声明一致性测试）

- [ ] **步骤 5：运行全量测试确认无回归**

```bash
cd /home/kali/.hermes/plugins/soul-context-injector && python3 -m pytest tests/ -v --tb=short 2>&1
```

预期：93+ 原有测试 + 新增测试全部 PASS

---

### 任务 4：实现 `pre_llm_call` 节流兜底清理

**文件：**
- 修改：`__init__.py:98-165`（pre_llm_call_hook 函数）

- [ ] **步骤 1：编写失败的测试**

在 `tests/test_tracker_cleanup.py` 追加：

```python
def test_throttled_cleanup_runs_at_most_once_per_hour(tracking_dir):
    """节流清理每小时最多执行一次"""
    import __init__ as soul_init
    from datetime import datetime

    # 创建过期文件
    old_dt = datetime.fromtimestamp(time.time() - 25 * 3600).isoformat()
    _create_tracker_file(tracking_dir, "s1", old_dt)
    _create_tracker_file(tracking_dir, "s2", old_dt)
    assert len(list(tracking_dir.glob("*.json"))) == 2

    # 第一次调用应触发清理
    soul_init._last_cleanup_ts = 0
    soul_init._throttled_cleanup()
    assert len(list(tracking_dir.glob("*.json"))) == 0

    # 创建新过期文件
    _create_tracker_file(tracking_dir, "s3", old_dt)

    # 立即再次调用不应触发清理（节流）
    soul_init._throttled_cleanup()
    assert len(list(tracking_dir.glob("*.json"))) == 1  # 未被清理


def test_throttled_cleanup_resets_after_interval(tracking_dir):
    """超过1小时后节流应重置"""
    import __init__ as soul_init
    from datetime import datetime

    old_dt = datetime.fromtimestamp(time.time() - 25 * 3600).isoformat()
    _create_tracker_file(tracking_dir, "s1", old_dt)

    # 模拟上次清理在2小时前
    soul_init._last_cleanup_ts = time.time() - 7200
    soul_init._throttled_cleanup()
    assert len(list(tracking_dir.glob("*.json"))) == 0
```

- [ ] **步骤 2：运行测试验证失败**

```bash
cd /home/kali/.hermes/plugins/soul-context-injector && python3 -m pytest tests/test_tracker_cleanup.py::test_throttled_cleanup_runs_at_most_once_per_hour tests/test_tracker_cleanup.py::test_throttled_cleanup_resets_after_interval -v --tb=short 2>&1
```

预期：FAIL — `_last_cleanup_ts` 和 `_throttled_cleanup` 不存在。

- [ ] **步骤 3：实现节流逻辑**

在 `__init__.py` 模块顶部（`_lazy_imports()` 之前）添加：

```python
import time as _time
_last_cleanup_ts = 0.0

def _throttled_cleanup():
    """节流清理：每小时最多执行一次"""
    global _last_cleanup_ts
    now = _time.time()
    if now - _last_cleanup_ts > 3600:
        _last_cleanup_ts = now
        try:
            from .enforcer import cleanup_expired_trackers
            cleanup_expired_trackers()
        except Exception as e:
            logger.error(f"[SOUL] 节流清理失败: {e}")
```

在 `pre_llm_call_hook` 函数末尾（`return None` 之前）添加调用：

```python
    # ... 原有逻辑 ...

    # 兜底清理：每小时最多1次（主清理在 on_session_end）
    _throttled_cleanup()

    return None
```

- [ ] **步骤 4：运行测试验证通过**

```bash
cd /home/kali/.hermes/plugins/soul-context-injector && python3 -m pytest tests/test_tracker_cleanup.py -v --tb=short 2>&1
```

预期：全部 PASS

- [ ] **步骤 5：运行全量测试确认无回归**

```bash
cd /home/kali/.hermes/plugins/soul-context-injector && python3 -m pytest tests/ -v --tb=short 2>&1
```

预期：全部 PASS

---

### 任务 5：一次性清理历史堆积文件

**文件：**
- 运行时：`~/.hermes/skill-tracking/*.json`

- [ ] **步骤 1：预检 — 确认清理范围**

```bash
echo "清理前统计："
ls ~/.hermes/skill-tracking/*.json 2>/dev/null | wc -l
echo "24小时前的文件（将被删除）："
find ~/.hermes/skill-tracking/ -name "*.json" -mmin +1440 | wc -l
echo "24小时内的文件（将被保留）："
find ~/.hermes/skill-tracking/ -name "*.json" -mmin -1440 | wc -l
```

- [ ] **步骤 2：执行清理**

```bash
find ~/.hermes/skill-tracking/ -name "*.json" -mmin +1440 -delete
```

- [ ] **步骤 3：验证清理结果**

```bash
echo "清理后统计："
ls ~/.hermes/skill-tracking/*.json 2>/dev/null | wc -l
echo "磁盘占用："
du -sh ~/.hermes/skill-tracking/
```

预期：剩余文件数 ≤ 当日会话数，磁盘占用 < 1MB

---

## 自检清单

| 检查项 | 状态 |
|--------|------|
| 规格覆盖度：追踪文件清理 → 任务1-5 全覆盖 | ✅ |
| 占位符扫描：无 TODO/待定/补充细节 | ✅ |
| 类型一致性：cleanup_expired_trackers / on_session_end_hook / _throttled_cleanup 命名一致 | ✅ |
| hooks 声明一致性：plugin.yaml vs __init__.py register() 由测试自动验证 | ✅ |
| 现有测试回归：93+ 原有测试不受影响 | ✅ |

## 执行交接

计划已完成。两种执行方式：

**1. 子代理驱动（推荐）** — 每个任务调度一个新的子代理，任务间进行审查，快速迭代

**2. 内联执行** — 在当前会话中使用 executing-plans 执行任务，批量执行并设有检查点

选哪种方式？
