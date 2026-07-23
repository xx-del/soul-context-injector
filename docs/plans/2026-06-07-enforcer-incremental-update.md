# Enforcer 增量更新机制实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 修复任务等级转换时已调用技能被清空的问题，实现增量更新机制

**Architecture:** 改造 enforcer.py 的 create_tracker() 函数，支持增量更新而非覆盖重写，保留已调用技能历史，添加文件锁保证并发安全

**Tech Stack:** Python 3, fcntl (文件锁), JSON, pathlib

---

## Task 1: 备份现有代码

**Files:**
- Create: `/home/kali/.hermes/plugins/soul-context-injector/enforcer.py.backup_20260607`

**Step 1: 备份当前 enforcer.py**

Run:
```bash
cp /home/kali/.hermes/plugins/soul-context-injector/enforcer.py /home/kali/.hermes/plugins/soul-context-injector/enforcer.py.backup_20260607
```

Expected: 无输出，文件已创建

**Step 2: 验证备份**

Run:
```bash
ls -la /home/kali/.hermes/plugins/soul-context-injector/enforcer.py*
```

Expected:
```
-rw-rw-r-- 1 kali kali 3XXX 6月  7日 XX:XX enforcer.py
-rw-rw-r-- 1 kali kali 3XXX 6月  7日 XX:XX enforcer.py.backup_20260514_145830
-rw-rw---- 1 kali kali 3XXX 6月  7日 XX:XX enforcer.py.backup_20260607
```

---

## Task 2: 添加文件锁工具函数

**Files:**
- Modify: `/home/kali/.hermes/plugins/soul-context-injector/enforcer.py:1-20` (导入区)

**Step 1: 添加必要的导入**

在文件顶部导入区添加：

```python
import fcntl
import contextlib
from typing import Dict, Any, List, Tuple, Optional
```

**Step 2: 添加文件锁上下文管理器**

在 `TRACKING_DIR` 定义后添加：

```python
@contextlib.contextmanager
def file_lock(file_path: Path, mode: str = "r"):
    """文件锁上下文管理器

    Args:
        file_path: 文件路径
        mode: 打开模式 ('r', 'w', 'a')
    """
    with open(file_path, mode, encoding='utf-8') as f:
        try:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)  # 排他锁
            yield f
        finally:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)  # 释放锁
```

**Step 3: 测试文件锁**

Run:
```bash
cd /home/kali/.hermes/plugins/soul-context-injector && python3 -c "
from pathlib import Path
from enforcer import file_lock
import tempfile

# 测试文件锁
with tempfile.NamedTemporaryFile(delete=False) as tmp:
    tmp_path = Path(tmp.name)

with file_lock(tmp_path, 'w') as f:
    f.write('test')

print('✅ 文件锁测试通过')
tmp_path.unlink()
"
```

Expected: `✅ 文件锁测试通过`

---

## Task 3: 添加辅助函数

**Files:**
- Modify: `/home/kali/.hermes/plugins/soul-context-injector/enforcer.py` (新增函数)

**Step 1: 添加 _check_completion 函数**

在 `file_lock` 函数后添加：

```python
def _check_completion(tracker: Dict) -> bool:
    """检查任务是否完成

    Args:
        tracker: 追踪器数据

    Returns:
        True 如果所有必需技能已调用
    """
    required = tracker.get("current", {}).get("required_skills", [])
    called = tracker.get("current", {}).get("called_skills", [])
    return all(s in called for s in required)
```

**Step 2: 添加 migrate_tracker 函数**

在 `_check_completion` 函数后添加：

```python
def migrate_tracker(old_tracker: Dict) -> Dict:
    """迁移旧格式追踪器到新格式

    Args:
        old_tracker: 旧格式追踪器数据

    Returns:
        新格式追踪器数据
    """
    return {
        "session_id": old_tracker.get("session_id"),
        "task_level": old_tracker.get("task_level"),
        "created_at": old_tracker.get("created_at"),
        "updated_at": old_tracker.get("updated_at", old_tracker.get("created_at")),
        "current": {
            "required_skills": old_tracker.get("required_skills", []),
            "called_skills": old_tracker.get("called_skills", [])
        },
        "history": [],
        "metadata": {
            "total_calls": len(old_tracker.get("called_skills", [])),
            "level_transitions": 0,
            "last_skill_at": None
        }
    }
```

**Step 3: 测试迁移函数**

Run:
```bash
cd /home/kali/.hermes/plugins/soul-context-injector && python3 -c "
from enforcer import migrate_tracker

old = {
    'session_id': 'test',
    'task_level': 'L2',
    'created_at': '2026-06-07T10:00:00',
    'called_skills': ['deep-thinking'],
    'required_skills': ['deep-thinking']
}

new = migrate_tracker(old)
assert new['current']['called_skills'] == ['deep-thinking']
assert new['history'] == []
assert new['metadata']['total_calls'] == 1
print('✅ 迁移函数测试通过')
"
```

Expected: `✅ 迁移函数测试通过`

---

## Task 4: 重写 create_tracker 函数

**Files:**
- Modify: `/home/kali/.hermes/plugins/soul-context-injector/enforcer.py:create_tracker`

**Step 1: 替换 create_tracker 函数**

找到 `def create_tracker(session_id: str, task_level: str) -> Path:` 函数，完整替换为：

```python
def create_tracker(session_id: str, task_level: str) -> Path:
    """创建或更新追踪器（增量模式）

    - 首次创建：初始化新追踪器
    - 等级相同：无操作
    - 等级转换：保存历史，更新当前任务

    Args:
        session_id: 会话 ID
        task_level: 任务等级（L0-L4, W, S）

    Returns:
        追踪文件路径
    """
    TRACKING_DIR.mkdir(parents=True, exist_ok=True)

    required_skills = SKILL_BINDINGS.get(task_level, [])
    tracker_file = TRACKING_DIR / f"{session_id}.json"

    # 尝试读取旧追踪器
    old_tracker = None
    if tracker_file.exists():
        try:
            with file_lock(tracker_file, "r") as f:
                old_data = json.load(f)
                # 检测旧格式并迁移
                if "current" not in old_data:
                    old_tracker = migrate_tracker(old_data)
                else:
                    old_tracker = old_data
        except Exception as e:
            logger.warning(f"读取旧追踪器失败: {e}")

    now = datetime.datetime.now().isoformat()

    # 首次创建
    if not old_tracker:
        tracker_data = {
            "session_id": session_id,
            "task_level": task_level,
            "created_at": now,
            "updated_at": now,
            "current": {
                "required_skills": required_skills,
                "called_skills": []
            },
            "history": [],
            "metadata": {
                "total_calls": 0,
                "level_transitions": 0,
                "last_skill_at": None
            }
        }
        logger.info(f"[ENFORCER] 创建追踪器: session={session_id}, level={task_level}")

    # 增量更新
    else:
        old_level = old_tracker.get("task_level")

        # 等级相同，无需更新
        if old_level == task_level:
            logger.debug(f"[ENFORCER] 等级相同，跳过更新: {session_id}")
            return tracker_file

        # 等级转换
        history_entry = {
            "level": old_level,
            "from": old_tracker.get("created_at"),
            "to": now,
            "required": old_tracker.get("current", {}).get("required_skills", []),
            "called": old_tracker.get("current", {}).get("called_skills", []),
            "completed": _check_completion(old_tracker)
        }

        # 限制历史长度（最多10条）
        history = old_tracker.get("history", [])
        history.append(history_entry)
        if len(history) > 10:
            history = history[-10:]

        tracker_data = {
            "session_id": session_id,
            "task_level": task_level,
            "created_at": old_tracker.get("created_at"),  # 保留创建时间
            "updated_at": now,
            "current": {
                "required_skills": required_skills,
                "called_skills": old_tracker.get("current", {}).get("called_skills", [])  # 保留已调用技能
            },
            "history": history,
            "metadata": {
                "total_calls": old_tracker.get("metadata", {}).get("total_calls", 0),
                "level_transitions": old_tracker.get("metadata", {}).get("level_transitions", 0) + 1,
                "last_skill_at": old_tracker.get("metadata", {}).get("last_skill_at")
            }
        }
        logger.info(f"[ENFORCER] 等级转换: {session_id}, {old_level} → {task_level}")

    # 写入文件（带锁）
    with file_lock(tracker_file, "w") as f:
        json.dump(tracker_data, f, ensure_ascii=False, indent=2)

    return tracker_file
```

**Step 2: 测试首次创建**

Run:
```bash
cd /home/kali/.hermes/plugins/soul-context-injector && python3 -c "
from enforcer import create_tracker, get_tracker
import os

session_id = 'test_create_new'

# 清理旧测试文件
tracker_file = Path.home() / '.hermes' / 'skill-tracking' / f'{session_id}.json'
if tracker_file.exists():
    tracker_file.unlink()

# 创建新追踪器
create_tracker(session_id, 'L2')

# 验证
tracker = get_tracker(session_id)
assert tracker['task_level'] == 'L2'
assert tracker['current']['required_skills'] == ['deep-thinking']
assert tracker['current']['called_skills'] == []
assert tracker['history'] == []
print('✅ 首次创建测试通过')

# 清理
tracker_file.unlink()
"
```

Expected: `✅ 首次创建测试通过`

---

## Task 5: 更新 get_tracker 函数

**Files:**
- Modify: `/home/kali/.hermes/plugins/soul-context-injector/enforcer.py:get_tracker`

**Step 1: 更新 get_tracker 支持新格式**

找到 `def get_tracker(session_id: str) -> Optional[Dict]:` 函数，替换为：

```python
def get_tracker(session_id: str) -> Optional[Dict[str, Any]]:
    """获取追踪器数据（带容错）

    Args:
        session_id: 会话 ID

    Returns:
        追踪器数据，如果不存在或损坏则返回 None
    """
    tracker_file = TRACKING_DIR / f"{session_id}.json"
    if not tracker_file.exists():
        return None

    try:
        with file_lock(tracker_file, "r") as f:
            data = json.load(f)
            # 检测旧格式并迁移
            if "current" not in data:
                return migrate_tracker(data)
            return data
    except json.JSONDecodeError as e:
        logger.error(f"追踪文件损坏: {e}")
        # 备份损坏文件
        backup_file = tracker_file.with_suffix(".json.corrupted")
        tracker_file.rename(backup_file)
        return None
    except Exception as e:
        logger.error(f"读取追踪文件失败: {e}")
        return None
```

**Step 2: 测试读取**

Run:
```bash
cd /home/kali/.hermes/plugins/soul-context-injector && python3 -c "
from enforcer import create_tracker, get_tracker
from pathlib import Path

session_id = 'test_get_tracker'
tracker_file = Path.home() / '.hermes' / 'skill-tracking' / f'{session_id}.json'

# 清理
if tracker_file.exists():
    tracker_file.unlink()

# 创建
create_tracker(session_id, 'L3')

# 读取
tracker = get_tracker(session_id)
assert tracker is not None
assert tracker['task_level'] == 'L3'
print('✅ 读取测试通过')

# 清理
tracker_file.unlink()
"
```

Expected: `✅ 读取测试通过`

---

## Task 6: 更新 update_tracker 函数

**Files:**
- Modify: `/home/kali/.hermes/plugins/soul-context-injector/enforcer.py:update_tracker`

**Step 1: 更新 update_tracker 使用文件锁**

找到 `def update_tracker(session_id: str, data: Dict):` 函数，替换为：

```python
def update_tracker(session_id: str, data: Dict[str, Any]) -> bool:
    """更新追踪器（带文件锁）

    Args:
        session_id: 会话 ID
        data: 追踪器数据

    Returns:
        True 如果成功，False 如果失败
    """
    tracker_file = TRACKING_DIR / f"{session_id}.json"
    try:
        with file_lock(tracker_file, "w") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        logger.error(f"更新追踪器失败: {e}")
        return False
```

---

## Task 7: 更新 track_skill_call 函数

**Files:**
- Modify: `/home/kali/.hermes/plugins/soul-context-injector/enforcer.py:track_skill_call`

**Step 1: 更新 track_skill_call 支持新格式**

找到 `def track_skill_call(session_id: str, skill_name: str) -> bool:` 函数，替换为：

```python
def track_skill_call(session_id: str, skill_name: str) -> bool:
    """追踪技能调用

    Args:
        session_id: 会话 ID
        skill_name: 技能名称

    Returns:
        True 如果成功追踪，False 如果失败或重复
    """
    tracker = get_tracker(session_id)
    if not tracker:
        logger.warning(f"追踪器不存在: {session_id}")
        return False

    called_skills = tracker.get("current", {}).get("called_skills", [])

    # 检查是否已调用（去重）
    if skill_name in called_skills:
        logger.debug(f"技能已调用过: {skill_name}")
        return False

    # 添加到已调用列表
    called_skills.append(skill_name)

    # 更新元数据
    metadata = tracker.get("metadata", {})
    metadata["total_calls"] = metadata.get("total_calls", 0) + 1
    metadata["last_skill_at"] = datetime.datetime.now().isoformat()

    # 更新追踪器
    return update_tracker(session_id, tracker)
```

**Step 2: 测试技能调用追踪**

Run:
```bash
cd /home/kali/.hermes/plugins/soul-context-injector && python3 -c "
from enforcer import create_tracker, track_skill_call, get_tracker
from pathlib import Path

session_id = 'test_track_skill'
tracker_file = Path.home() / '.hermes' / 'skill-tracking' / f'{session_id}.json'

# 清理
if tracker_file.exists():
    tracker_file.unlink()

# 创建追踪器
create_tracker(session_id, 'L3')

# 追踪技能调用
result1 = track_skill_call(session_id, 'deep-thinking')
assert result1 == True

result2 = track_skill_call(session_id, 'openclaw-behavior-plan')
assert result2 == True

# 验证
tracker = get_tracker(session_id)
assert 'deep-thinking' in tracker['current']['called_skills']
assert 'openclaw-behavior-plan' in tracker['current']['called_skills']
assert tracker['metadata']['total_calls'] == 2
print('✅ 技能追踪测试通过')

# 清理
tracker_file.unlink()
"
```

Expected: `✅ 技能追踪测试通过`

---

## Task 8: 更新 check_required_skills 函数

**Files:**
- Modify: `/home/kali/.hermes/plugins/soul-context-injector/enforcer.py:check_required_skills`

**Step 1: 更新 check_required_skills 支持历史技能**

找到 `def check_required_skills(session_id: str) -> Tuple[bool, Optional[str]]:` 函数，替换为：

```python
def check_required_skills(session_id: str) -> Tuple[bool, Optional[str]]:
    """检查必需技能是否已调用（包含历史）

    Args:
        session_id: 会话 ID

    Returns:
        (True, None) 如果所有技能已调用
        (False, error_message) 如果缺少技能
    """
    tracker = get_tracker(session_id)
    if not tracker:
        return True, None

    # 当前任务必需技能
    required = tracker.get("current", {}).get("required_skills", [])

    # 已调用技能（包含历史）
    called = set(tracker.get("current", {}).get("called_skills", []))
    for h in tracker.get("history", []):
        called.update(h.get("called", []))

    # 计算缺失技能
    missing = [s for s in required if s not in called]

    if missing:
        return False, _build_error_message(tracker, missing, called)

    return True, None


def _build_error_message(tracker: Dict, missing: List[str], called: set) -> str:
    """构建错误消息"""
    task_level = tracker.get("task_level")
    called_str = ", ".join(sorted(called)) if called else "无"

    return f"""【规则违反】

未调用必须技能: {', '.join(missing)}

当前任务等级: {task_level}
已调用技能: {called_str}

---

【正确流程】

1. 先调用必须技能（{', '.join(missing)}）
2. 完成技能要求的分析/方案生成
3. 再输出结果

---

⚠️ 此拦截由 soul-context-injector 强制执行机制触发
"""
```

**Step 2: 测试技能检查**

Run:
```bash
cd /home/kali/.hermes/plugins/soul-context-injector && python3 -c "
from enforcer import create_tracker, track_skill_call, check_required_skills
from pathlib import Path

session_id = 'test_check_skills'
tracker_file = Path.home() / '.hermes' / 'skill-tracking' / f'{session_id}.json'

# 清理
if tracker_file.exists():
    tracker_file.unlink()

# 创建追踪器
create_tracker(session_id, 'L3')

# 检查（应该失败）
all_called, error = check_required_skills(session_id)
assert all_called == False
assert 'deep-thinking' in error
assert 'openclaw-behavior-plan' in error
print('✅ 缺少技能检测通过')

# 调用一个技能
track_skill_call(session_id, 'deep-thinking')

# 检查（应该仍失败）
all_called, error = check_required_skills(session_id)
assert all_called == False
assert 'openclaw-behavior-plan' in error
print('✅ 部分缺少检测通过')

# 调用剩余技能
track_skill_call(session_id, 'openclaw-behavior-plan')

# 检查（应该成功）
all_called, error = check_required_skills(session_id)
assert all_called == True
assert error is None
print('✅ 全部调用检测通过')

# 清理
tracker_file.unlink()
"
```

Expected:
```
✅ 缺少技能检测通过
✅ 部分缺少检测通过
✅ 全部调用检测通过
```

---

## Task 9: 集成测试 - 等级转换

**Files:**
- Test: `/home/kali/.hermes/plugins/soul-context-injector/test_level_transition.py`

**Step 1: 创建集成测试文件**

```python
#!/usr/bin/env python3
"""集成测试：任务等级转换"""

import sys
from pathlib import Path

# 添加插件路径
sys.path.insert(0, str(Path(__file__).parent))

from enforcer import (
    create_tracker,
    track_skill_call,
    check_required_skills,
    get_tracker,
    TRACKING_DIR
)


def test_l2_to_l3():
    """测试 L2 → L3 等级转换"""
    session_id = "test_l2_to_l3"
    tracker_file = TRACKING_DIR / f"{session_id}.json"

    # 清理
    if tracker_file.exists():
        tracker_file.unlink()

    print("\n=== 测试 L2 → L3 等级转换 ===")

    # Phase 1: L2 任务
    print("\n1. 创建 L2 追踪器")
    create_tracker(session_id, "L2")

    print("2. 调用 deep-thinking")
    track_skill_call(session_id, "deep-thinking")

    print("3. 检查 L2 完成")
    all_called, _ = check_required_skills(session_id)
    assert all_called == True, "L2 应该已完成"
    print("   ✅ L2 完成")

    # Phase 2: L3 任务（等级转换）
    print("\n4. 转换到 L3")
    create_tracker(session_id, "L3")

    print("5. 验证 deep-thinking 保留")
    tracker = get_tracker(session_id)
    assert "deep-thinking" in tracker["current"]["called_skills"], "deep-thinking 应该保留"
    print("   ✅ deep-thinking 已保留")

    print("6. 检查 L3 状态")
    all_called, error = check_required_skills(session_id)
    assert all_called == False, "L3 应该未完成"
    assert "openclaw-behavior-plan" in error, "应该缺少 openclaw-behavior-plan"
    print(f"   ✅ 正确检测到缺少技能")

    print("7. 调用 openclaw-behavior-plan")
    track_skill_call(session_id, "openclaw-behavior-plan")

    print("8. 检查 L3 完成")
    all_called, _ = check_required_skills(session_id)
    assert all_called == True, "L3 应该已完成"
    print("   ✅ L3 完成")

    # 验证历史
    print("\n9. 验证历史记录")
    tracker = get_tracker(session_id)
    assert len(tracker["history"]) == 1, "应该有 1 条历史"
    assert tracker["history"][0]["level"] == "L2", "历史应该是 L2"
    assert tracker["history"][0]["completed"] == True, "L2 应该标记为完成"
    print("   ✅ 历史记录正确")

    # 清理
    tracker_file.unlink()
    print("\n✅ L2 → L3 测试通过\n")


def test_l3_to_l4():
    """测试 L3 → L4 等级转换"""
    session_id = "test_l3_to_l4"
    tracker_file = TRACKING_DIR / f"{session_id}.json"

    # 清理
    if tracker_file.exists():
        tracker_file.unlink()

    print("\n=== 测试 L3 → L4 等级转换 ===")

    # Phase 1: L3 任务
    print("\n1. 创建 L3 追踪器")
    create_tracker(session_id, "L3")

    print("2. 调用技能")
    track_skill_call(session_id, "deep-thinking")
    track_skill_call(session_id, "openclaw-behavior-plan")

    # Phase 2: L4 任务
    print("3. 转换到 L4")
    create_tracker(session_id, "L4")

    print("4. 验证历史技能保留")
    tracker = get_tracker(session_id)
    assert "deep-thinking" in tracker["current"]["called_skills"]
    print("   ✅ 历史技能保留")

    print("5. 检查 L4 状态")
    all_called, error = check_required_skills(session_id)
    assert all_called == False, "L4 应该未完成"
    assert "planning-with-files" in error
    print("   ✅ 正确检测到缺少技能")

    # 清理
    tracker_file.unlink()
    print("\n✅ L3 → L4 测试通过\n")


if __name__ == "__main__":
    test_l2_to_l3()
    test_l3_to_l4()
    print("\n🎉 所有集成测试通过！\n")
```

**Step 2: 运行集成测试**

Run:
```bash
cd /home/kali/.hermes/plugins/soul-context-injector && python3 test_level_transition.py
```

Expected:
```
=== 测试 L2 → L3 等级转换 ===
...
✅ L2 → L3 测试通过

=== 测试 L3 → L4 等级转换 ===
...
✅ L3 → L4 测试通过

🎉 所有集成测试通过！
```

**Step 3: 提交测试文件**

Run:
```bash
cd /home/kali/.hermes/plugins/soul-context-injector && git add test_level_transition.py && git commit -m "test: add level transition integration tests"
```

---

## Task 10: 更新版本号和文档

**Files:**
- Modify: `/home/kali/.hermes/plugins/soul-context-injector/__init__.py:1`
- Modify: `/home/kali/.hermes/plugins/soul-context-injector/CHANGELOG.md`

**Step 1: 更新版本号**

在 `__init__.py` 顶部修改版本注释：

```python
"""
Soul Context Injector - Hermes Plugin v5.10.0

核心改进：
- 增量更新机制：任务等级转换时保留已调用技能
- 文件锁支持：防止并发写入冲突
- 历史记录：记录完整的等级转换链

四层拦截体系：
- Layer 0: 强制执行检查（技能调用追踪）
- Layer 1: 技能白名单放行
- Layer 2: 破坏性命令拦截
- Layer 3: 工作流完整性检查

...
"""
```

**Step 2: 更新 CHANGELOG**

在 `CHANGELOG.md` 顶部添加：

```markdown
## [5.10.0] - 2026-06-07

### Added
- 增量更新机制：任务等级转换时保留已调用技能历史
- 文件锁支持（fcntl.flock）：防止并发写入冲突
- 等级转换历史记录：最多保留 10 条转换记录
- 自动迁移：旧格式追踪文件自动迁移到新格式

### Fixed
- 修复任务等级转换（L2→L3→L4）时已调用技能被清空的问题
- 修复并发写入可能导致的数据损坏

### Changed
- 追踪器数据结构升级：新增 `current`、`history`、`metadata` 字段
- `create_tracker()` 改为增量更新模式
- `check_required_skills()` 现在包含历史技能检查
```

**Step 3: 提交更改**

Run:
```bash
cd /home/kali/.hermes/plugins/soul-context-injector && git add __init__.py CHANGELOG.md enforcer.py && git commit -m "feat: add incremental update mechanism for skill tracking

- Fix: skill calls cleared during level transitions (L2→L3→L4)
- Add: file lock support for concurrent safety
- Add: level transition history (max 10 entries)
- Add: auto migration from old format

BREAKING CHANGE: tracker data structure updated"
```

---

## Task 11: 清理和验证

**Step 1: 清理备份文件（可选）**

Run:
```bash
# 保留最新的备份，删除旧备份
ls -la /home/kali/.hermes/plugins/soul-context-injector/enforcer.py.backup*
```

**Step 2: 运行完整测试套件**

Run:
```bash
cd /home/kali/.hermes/plugins/soul-context-injector && python3 -m pytest test_level_transition.py -v
```

**Step 3: 验证插件加载**

Run:
```bash
cd /home/kali/.hermes/plugins/soul-context-injector && python3 -c "
from enforcer import should_enforce, create_tracker, check_required_skills
print('✅ 插件加载成功')
"
```

Expected: `✅ 插件加载成功`

---

## Summary

### Files Modified
- `/home/kali/.hermes/plugins/soul-context-injector/enforcer.py` - 核心逻辑
- `/home/kali/.hermes/plugins/soul-context-injector/__init__.py` - 版本号
- `/home/kali/.hermes/plugins/soul-context-injector/CHANGELOG.md` - 更新日志

### Files Created
- `/home/kali/.hermes/plugins/soul-context-injector/test_level_transition.py` - 集成测试
- `/home/kali/.hermes/plugins/soul-context-injector/enforcer.py.backup_20260607` - 备份

### Key Changes
1. **增量更新**：`create_tracker()` 不再清空已调用技能
2. **文件锁**：防止并发写入冲突
3. **历史记录**：记录等级转换链
4. **向后兼容**：自动迁移旧格式

### Risk Mitigation
- 备份现有代码
- 完整的单元测试和集成测试
- 向后兼容旧格式追踪文件
- 文件锁防止并发问题
