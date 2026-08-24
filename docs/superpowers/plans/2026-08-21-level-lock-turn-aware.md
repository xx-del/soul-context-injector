# Level-Lock 轮次化修复 实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 修复 soul-context-injector 的 Level-Lock 机制，使同等级的新用户请求也能触发 L2/L3/L4 上下文注入，而非被"同等级跳过"逻辑阻断。

**架构：** 在 `state.py` 的 `_injected_levels` 中增加 `msg_count` 字段，用 `conversation_history` 长度作为轮次指示器。同等级+同轮次才跳过，不同轮次（新请求）重新注入。同时在 `enforcer.py` 的 `create_tracker` 中增加 `force_reset` 参数，新请求时清空 `called_skills`。

**技术栈：** Python 3.14, pytest, unittest.mock

---

## 文件结构

| 文件 | 职责 | 变更类型 |
|------|------|---------|
| `state.py` | 注入等级追踪数据结构 | 修改：`_injected_levels` 增加 `msg_count`；新增 `should_skip_injection()` |
| `__init__.py` | pre_llm_call_hook 轮次判断 | 修改：用 `conversation_history` 长度做跳过判断 |
| `enforcer.py` | 追踪器创建/重置 | 修改：`create_tracker` 新增 `force_reset` 参数 |
| `tests/test_level_lock_turn.py` | 轮次级锁定测试 | 新建：覆盖所有场景 |
| `tests/test_level_transition_injection.py` | 现有等级转换测试 | 修改：适配新接口 |

---

## 任务 1: state.py — 数据结构扩展

**文件：**
- 修改：`state.py:97-109`

- [ ] **步骤 1：编写失败的测试**

在 `tests/test_level_lock_turn.py` 创建：

```python
"""Level-Lock 轮次化测试。测试同等级新请求能触发注入。"""
import pytest
from unittest.mock import MagicMock


class TestShouldSkipInjection:
    """should_skip_injection 应同时比较 level 和 msg_count。"""

    def test_same_level_same_turn_skips(self, state):
        """同等级+同轮次 → 跳过"""
        state.set_last_injected_level("s1", "L2", msg_count=5)
        assert state.should_skip_injection("s1", "L2", 5) is True

    def test_same_level_different_turn_injects(self, state):
        """同等级+不同轮次 → 不跳过（新请求）"""
        state.set_last_injected_level("s1", "L2", msg_count=5)
        assert state.should_skip_injection("s1", "L2", 6) is False

    def test_different_level_injects(self, state):
        """不同等级 → 不跳过"""
        state.set_last_injected_level("s1", "L2", msg_count=5)
        assert state.should_skip_injection("s1", "L4", 5) is False

    def test_no_prior_injection(self, state):
        """无历史记录 → 不跳过"""
        assert state.should_skip_injection("new_session", "L2", 0) is False

    def test_get_returns_level_only(self, state):
        """get_last_injected_level 仍返回等级字符串（向后兼容）"""
        state.set_last_injected_level("s1", "L3", msg_count=10)
        assert state.get_last_injected_level("s1") == "L3"

    def test_get_returns_none_for_unknown(self, state):
        """未知 session 返回 None"""
        assert state.get_last_injected_level("unknown") is None
```

- [ ] **步骤 2：运行测试验证失败**

运行：`cd /home/kali/.hermes/plugins/soul-context-injector && python -m pytest tests/test_level_lock_turn.py -v`
预期：FAIL — `set_last_injected_level` 不接受 `msg_count` 参数，`should_skip_injection` 不存在

- [ ] **步骤 3：修改 state.py 数据结构**

将 `state.py` 第 97-109 行从：

```python
# ============ 注入等级追踪 ============
_injected_levels: Dict[str, str] = {}  # session_id → task_level


def get_last_injected_level(session_id: str) -> Optional[str]:
    """获取某 session 最近一次注入的任务等级"""
    return _injected_levels.get(session_id)


def set_last_injected_level(session_id: str, level: str) -> None:
    """记录某 session 注入的任务等级"""
    if level:
        _injected_levels[session_id] = level
```

改为：

```python
# ============ 注入等级追踪 ============
_injected_levels: Dict[str, Dict[str, Any]] = {}  # session_id → {level, msg_count}


def get_last_injected_level(session_id: str) -> Optional[str]:
    """获取某 session 最近一次注入的任务等级（向后兼容）"""
    data = _injected_levels.get(session_id)
    return data["level"] if data else None


def set_last_injected_level(session_id: str, level: str, msg_count: int = 0) -> None:
    """记录某 session 注入的任务等级和轮次

    Args:
        session_id: 会话 ID
        level: 任务等级
        msg_count: 注入时的 conversation_history 长度
    """
    if level:
        _injected_levels[session_id] = {"level": level, "msg_count": msg_count}


def should_skip_injection(session_id: str, new_level: str, current_msg_count: int) -> bool:
    """判断是否应跳过注入（同等级+同轮次才跳过）

    Args:
        session_id: 会话 ID
        new_level: 当前消息的任务等级
        current_msg_count: 当前 conversation_history 长度

    Returns:
        True 如果应跳过（同等级+同轮次），False 如果应注入
    """
    data = _injected_levels.get(session_id)
    if not data:
        return False
    return data["level"] == new_level and data["msg_count"] == current_msg_count
```

- [ ] **步骤 4：运行测试验证通过**

运行：`cd /home/kali/.hermes/plugins/soul-context-injector && python -m pytest tests/test_level_lock_turn.py -v`
预期：6 passed

- [ ] **步骤 5：运行现有测试确保无回归**

运行：`cd /home/kali/.hermes/plugins/soul-context-injector && python -m pytest tests/ -v --tb=short`
预期：所有现有测试通过（`set_last_injected_level` 新参数有默认值 `msg_count=0`，向后兼容）

- [ ] **步骤 6：Commit**

```bash
cd /home/kali/.hermes/plugins/soul-context-injector
git add state.py tests/test_level_lock_turn.py
git commit -m "feat(state): add msg_count to level-lock for turn-aware injection

- _injected_levels stores {level, msg_count} instead of just level
- get_last_injected_level returns level string (backward compatible)
- set_last_injected_level accepts optional msg_count parameter
- should_skip_injection compares both level AND msg_count
- Same level + same turn = skip; same level + new turn = inject"
```

---

## 任务 2: __init__.py — 轮次判断逻辑

**文件：**
- 修改：`__init__.py:175-180`（Layer 0.5 逻辑）

- [ ] **步骤 1：编写失败的测试**

在 `tests/test_level_lock_turn.py` 追加：

```python
class TestPreLLMTurnAwareInjection:
    """pre_llm_call_hook 应基于轮次判断是否跳过注入。"""

    def test_same_level_new_turn_injects(self, soul_init):
        """同等级+新轮次（conversation_history 增长）→ 应注入"""
        session_id = "test_turn_new"
        # 第1轮：空 history
        result1 = soul_init.pre_llm_call_hook(
            user_message="分析漏洞",
            session_id=session_id,
            conversation_history=[],
            is_first_turn=False,
            model="test", platform="test",
        )
        assert result1 is not None, "第1轮应注入"

        # 第2轮：history 增长（模拟新消息）
        result2 = soul_init.pre_llm_call_hook(
            user_message="分析另一个漏洞",
            session_id=session_id,
            conversation_history=[{"role": "user", "content": "分析漏洞"}, {"role": "assistant", "content": "..."}],
            is_first_turn=False,
            model="test", platform="test",
        )
        assert result2 is not None, "同等级新轮次应重新注入"

    def test_same_level_same_turn_skips(self, soul_init):
        """同等级+同轮次（conversation_history 不变）→ 应跳过"""
        session_id = "test_turn_skip"
        history = [{"role": "user", "content": "分析漏洞"}, {"role": "assistant", "content": "..."}]

        # 第1轮
        result1 = soul_init.pre_llm_call_hook(
            user_message="分析漏洞",
            session_id=session_id,
            conversation_history=history,
            is_first_turn=False,
            model="test", platform="test",
        )
        assert result1 is not None, "第1轮应注入"

        # 第2轮：相同 history（同轮次重复触发）
        result2 = soul_init.pre_llm_call_hook(
            user_message="分析漏洞",
            session_id=session_id,
            conversation_history=history,
            is_first_turn=False,
            model="test", platform="test",
        )
        assert result2 is None, "同等级同轮次应跳过"

    def test_three_messages_all_inject(self, soul_init):
        """连续3条 L2 消息，每条新轮次都应注入"""
        session_id = "test_three_msgs"
        results = []
        for i in range(3):
            history = [{"role": "user", "content": f"msg{j}"} for j in range(i)]
            result = soul_init.pre_llm_call_hook(
                user_message=f"分析任务{i}",
                session_id=session_id,
                conversation_history=history,
                is_first_turn=False,
                model="test", platform="test",
            )
            results.append(result is not None)

        assert results == [True, True, True], f"每条新消息都应注入，实际: {results}"
```

- [ ] **步骤 2：运行测试验证失败**

运行：`cd /home/kali/.hermes/plugins/soul-context-injector && python -m pytest tests/test_level_lock_turn.py::TestPreLLMTurnAwareInjection -v`
预期：FAIL — `test_same_level_new_turn_injects` 失败（第2轮被跳过）

- [ ] **步骤 3：修改 __init__.py Layer 0.5 逻辑**

将 `__init__.py` 第 175-180 行从：

```python
        # Layer 0.5: 同等级跳过重复注入（替代原 whitelist+active_skill 检查）
        last_level = get_last_injected_level(session_id)
        if task_level == last_level:
            logger.debug(f"[SOUL] 等级未变({task_level})，跳过重复注入")
            return None
        set_last_injected_level(session_id, task_level)
```

改为：

```python
        # Layer 0.5: 同等级+同轮次跳过注入（不同轮次=新请求，需重新注入）
        msg_count = len(conversation_history)
        from .state import should_skip_injection
        if should_skip_injection(session_id, task_level, msg_count):
            logger.debug(f"[SOUL] 同等级同轮次({task_level}, msgs={msg_count})，跳过注入")
            return None
        set_last_injected_level(session_id, task_level, msg_count)
```

- [ ] **步骤 4：运行测试验证通过**

运行：`cd /home/kali/.hermes/plugins/soul-context-injector && python -m pytest tests/test_level_lock_turn.py -v`
预期：9 passed（6 个 state 测试 + 3 个 hook 测试）

- [ ] **步骤 5：运行现有测试确保无回归**

运行：`cd /home/kali/.hermes/plugins/soul-context-injector && python -m pytest tests/test_level_transition_injection.py -v --tb=short`

注意：`test_same_level_skips_injection` 现在使用 `conversation_history=[]`（msg_count=0），两次调用都是 msg_count=0，所以仍然跳过——旧行为保持。但如果该测试期望"同等级跳过"，需要确认其 history 是否变化。检查现有测试：两次调用都传 `conversation_history=[]`，msg_count 都是 0 → `should_skip_injection` 返回 True → 跳过 → 测试仍通过。

预期：5 passed（现有测试不受影响）

- [ ] **步骤 6：Commit**

```bash
cd /home/kali/.hermes/plugins/soul-context-injector
git add __init__.py tests/test_level_lock_turn.py
git commit -m "feat(init): use conversation_history length for turn-aware level-lock

- Layer 0.5 now compares both level AND msg_count
- Same level + same turn = skip (unchanged behavior)
- Same level + new turn = inject (fixed: new request gets rules)
- Uses len(conversation_history) as natural turn counter"
```

---

## 任务 3: enforcer.py — Tracker 轮次重置

**文件：**
- 修改：`enforcer.py:114-211`（create_tracker 函数）

- [ ] **步骤 1：编写失败的测试**

在 `tests/test_level_lock_turn.py` 追加：

```python
class TestTrackerForceReset:
    """create_tracker force_reset 应在新请求时清空 called_skills。"""

    def test_force_reset_clears_called_skills(self, temp_tracking_dir):
        """force_reset=True 时 called_skills 应被清空"""
        from enforcer import create_tracker, get_tracker, track_skill_call

        session_id = "test_force_reset"
        # 创建 tracker 并调用技能
        create_tracker(session_id, "L2")
        track_skill_call(session_id, "deep-thinking")

        tracker = get_tracker(session_id)
        assert "deep-thinking" in tracker["current"]["called_skills"]

        # force_reset 重置
        create_tracker(session_id, "L2", force_reset=True)

        tracker = get_tracker(session_id)
        assert tracker["current"]["called_skills"] == [], \
            f"force_reset 应清空 called_skills，实际: {tracker['current']['called_skills']}"

    def test_force_reset_preserves_level_and_history(self, temp_tracking_dir):
        """force_reset 应保留等级和历史"""
        from enforcer import create_tracker, get_tracker, track_skill_call

        session_id = "test_force_preserve"
        create_tracker(session_id, "L2")
        track_skill_call(session_id, "deep-thinking")

        # 等级转换 L2→L3，保留历史
        create_tracker(session_id, "L3")
        create_tracker(session_id, "L3", force_reset=True)

        tracker = get_tracker(session_id)
        assert tracker["task_level"] == "L3"
        assert len(tracker["history"]) >= 1  # L2→L3 历史保留

    def test_no_force_reset_preserves_called_skills(self, temp_tracking_dir):
        """force_reset=False（默认）时 called_skills 应保留"""
        from enforcer import create_tracker, get_tracker, track_skill_call

        session_id = "test_no_reset"
        create_tracker(session_id, "L2")
        track_skill_call(session_id, "deep-thinking")

        # 不 force_reset
        create_tracker(session_id, "L2")

        tracker = get_tracker(session_id)
        assert "deep-thinking" in tracker["current"]["called_skills"]
```

- [ ] **步骤 2：运行测试验证失败**

运行：`cd /home/kali/.hermes/plugins/soul-context-injector && python -m pytest tests/test_level_lock_turn.py::TestTrackerForceReset -v`
预期：FAIL — `create_tracker` 不接受 `force_reset` 参数

- [ ] **步骤 3：修改 enforcer.py create_tracker**

将 `enforcer.py` 第 114 行函数签名和第 164-171 行增量更新逻辑修改：

函数签名改为：
```python
def create_tracker(session_id: str, task_level: str, force_reset: bool = False) -> Path:
```

第 164-171 行从：
```python
    # 增量更新
    else:
        old_level = old_tracker.get("task_level")

        # 等级相同，无需更新
        if old_level == task_level:
            logger.debug(f"[SOUL-ENFORCER] 等级相同，跳过更新: {session_id}")
            return tracker_file
```

改为：
```python
    # 增量更新
    else:
        old_level = old_tracker.get("task_level")

        # 等级相同
        if old_level == task_level:
            if force_reset:
                # 新请求：重置 called_skills，保留等级和历史
                tracker_data = {
                    "session_id": session_id,
                    "task_level": task_level,
                    "created_at": old_tracker.get("created_at"),
                    "updated_at": now,
                    "current": {
                        "required_skills": required_skills,
                        "called_skills": []
                    },
                    "history": old_tracker.get("history", []),
                    "metadata": {
                        "total_calls": old_tracker.get("metadata", {}).get("total_calls", 0),
                        "level_transitions": old_tracker.get("metadata", {}).get("level_transitions", 0),
                        "last_skill_at": None
                    }
                }
                logger.info(f"[SOUL-ENFORCER] 新请求重置追踪器: {session_id}")
            else:
                logger.debug(f"[SOUL-ENFORCER] 等级相同，跳过更新: {session_id}")
                return tracker_file
```

- [ ] **步骤 4：运行测试验证通过**

运行：`cd /home/kali/.hermes/plugins/soul-context-injector && python -m pytest tests/test_level_lock_turn.py -v`
预期：12 passed

- [ ] **步骤 5：运行现有测试确保无回归**

运行：`cd /home/kali/.hermes/plugins/soul-context-injector && python -m pytest tests/test_incremental_update.py tests/test_level_transition_injection.py -v --tb=short`
预期：所有测试通过（`force_reset` 默认 False，旧行为不变）

- [ ] **步骤 6：Commit**

```bash
cd /home/kali/.hermes/plugins/soul-context-injector
git add enforcer.py tests/test_level_lock_turn.py
git commit -m "feat(enforcer): add force_reset to create_tracker for new requests

- force_reset=True clears called_skills while preserving level/history
- force_reset=False (default) preserves existing behavior
- Enables same-level new requests to re-trigger skill enforcement"
```

---

## 任务 4: __init__.py — 集成 force_reset

**文件：**
- 修改：`__init__.py:193-196`（create_tracker 调用处）

- [ ] **步骤 1：编写失败的测试**

在 `tests/test_level_lock_turn.py` 追加：

```python
class TestTrackerResetOnNewRequest:
    """新请求应重置 tracker 的 called_skills。"""

    def test_new_request_resets_tracker(self, soul_init, temp_tracking_dir):
        """同等级新请求 → tracker 重置 → post_llm_call 可重新注入"""
        from enforcer import create_tracker, get_tracker, track_skill_call

        session_id = "test_tracker_reset"

        # 第1轮：L2 注入
        soul_init.pre_llm_call_hook(
            user_message="分析漏洞",
            session_id=session_id,
            conversation_history=[],
            is_first_turn=False,
            model="test", platform="test",
        )

        # 模拟 AI 调用 deep-thinking
        track_skill_call(session_id, "deep-thinking")

        # 第2轮：新请求
        soul_init.pre_llm_call_hook(
            user_message="分析另一个漏洞",
            session_id=session_id,
            conversation_history=[{"role": "user", "content": "分析漏洞"}, {"role": "assistant", "content": "..."}],
            is_first_turn=False,
            model="test", platform="test",
        )

        # 验证 tracker 被重置
        tracker = get_tracker(session_id)
        assert tracker["current"]["called_skills"] == [], \
            f"新请求应重置 called_skills，实际: {tracker['current']['called_skills']}"
```

- [ ] **步骤 2：运行测试验证失败**

运行：`cd /home/kali/.hermes/plugins/soul-context-injector && python -m pytest tests/test_level_lock_turn.py::TestTrackerResetOnNewRequest -v`
预期：FAIL — `create_tracker` 调用未传 `force_reset`

- [ ] **步骤 3：修改 __init__.py create_tracker 调用**

将 `__init__.py` 第 193-196 行从：

```python
        # 4. 创建技能追踪（L2/L3/L4/W 任务）
        if task_level in ["L2", "L3", "L4", "W"]:
            from .enforcer import create_tracker
            create_tracker(session_id, task_level)
```

改为：

```python
        # 4. 创建技能追踪（L2/L3/L4/W 任务）
        #    新请求时 force_reset 清空 called_skills，确保每轮重新强制
        if task_level in ["L2", "L3", "L4", "W"]:
            from .enforcer import create_tracker
            is_new_request = not should_skip_injection(session_id, task_level, msg_count)
            create_tracker(session_id, task_level, force_reset=is_new_request)
```

注意：需要在 `should_skip_injection` 调用前已经 import 了它。检查任务 2 的改动——已在 Layer 0.5 处 `from .state import should_skip_injection`，但该 import 在函数作用域内。需要确保此处也能访问。最简单的方式是将 import 移到函数顶部或在调用处再次 import。

推荐方式：在第 193 行前补充 import：
```python
        if task_level in ["L2", "L3", "L4", "W"]:
            from .enforcer import create_tracker
            from .state import should_skip_injection as _ssi
            is_new_request = not _ssi(session_id, task_level, msg_count)
            create_tracker(session_id, task_level, force_reset=is_new_request)
```

- [ ] **步骤 4：运行测试验证通过**

运行：`cd /home/kali/.hermes/plugins/soul-context-injector && python -m pytest tests/test_level_lock_turn.py -v`
预期：13 passed

- [ ] **步骤 5：全量测试回归**

运行：`cd /home/kali/.hermes/plugins/soul-context-injector && python -m pytest tests/ -v --tb=short`
预期：所有测试通过

- [ ] **步骤 6：Commit**

```bash
cd /home/kali/.hermes/plugins/soul-context-injector
git add __init__.py tests/test_level_lock_turn.py
git commit -m "feat(init): integrate force_reset into create_tracker call

- New requests (different turn) trigger force_reset=True
- Same-turn calls use force_reset=False (default)
- Ensures tracker called_skills is cleared for each new analysis request"
```

---

## 任务 5: 修复现有测试 + 更新注释

**文件：**
- 修改：`tests/test_level_transition_injection.py:7-28`（test_same_level_skips_injection）
- 修改：`__init__.py:175` 注释
- 修改：`__init__.py:429` 版本号

- [ ] **步骤 1：更新 test_same_level_skips_injection**

现有测试 `test_same_level_skips_injection` 两次调用都传 `conversation_history=[]`，msg_count 都是 0 → 仍然跳过。测试逻辑不变，但注释应更新以反映新机制。

将 `tests/test_level_transition_injection.py` 第 7-28 行注释更新：

```python
    def test_same_level_skips_injection(self, soul_init):
        """同等级+同轮次（conversation_history 不变）应跳过注入"""
```

- [ ] **步骤 2：更新 __init__.py 版本号**

将 `__init__.py` 第 1 行 `v5.11.0` 改为 `v5.12.0`（或下一个版本号），第 429 行日志版本号同步更新。

- [ ] **步骤 3：全量测试回归**

运行：`cd /home/kali/.hermes/plugins/soul-context-injector && python -m pytest tests/ -v --tb=short`
预期：所有测试通过

- [ ] **步骤 4：Commit**

```bash
cd /home/kali/.hermes/plugins/soul-context-injector
git add __init__.py tests/test_level_transition_injection.py
git commit -m "chore: update version and test comments for turn-aware level-lock

- Version bump to v5.12.0
- Updated test comments to reflect new turn-aware behavior"
```

---

## 自检

**1. 规格覆盖度：**
- ✅ 同等级新轮次注入 — 任务 2 test_same_level_new_turn_injects
- ✅ 同等级同轮次跳过 — 任务 2 test_same_level_same_turn_skips
- ✅ 连续多条消息 — 任务 2 test_three_messages_all_inject
- ✅ Tracker 重置 — 任务 3 + 任务 4
- ✅ 向后兼容 — 任务 1 test_get_returns_level_only
- ✅ 现有测试无回归 — 每个任务步骤 5

**2. 占位符扫描：** 无 TODO/待定/后续实现

**3. 类型一致性：**
- `set_last_injected_level(session_id, level, msg_count)` — 任务 1 定义，任务 2 调用
- `should_skip_injection(session_id, new_level, current_msg_count)` — 任务 1 定义，任务 2+4 调用
- `create_tracker(session_id, task_level, force_reset=False)` — 任务 3 定义，任务 4 调用
- 所有参数名和类型一致 ✓
