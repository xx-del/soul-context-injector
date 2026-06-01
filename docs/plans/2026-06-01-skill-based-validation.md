# Soul-Context-Injector 技能验证重构方案

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**目标:** 将基于文件的 L4 验证替换为基于技能调用的验证，支持优雅回退。

**架构:**
- 移除文件搜索逻辑，改为追踪 `skill_view()` 调用
- 验证实际执行（delegate_task, agent_pool_client）
- 逃生舱机制：7次拦截后自动放行并建议回退到 L3/L2

**技术栈:** Python, Hermes Agent Plugin System, JSON 文件追踪

---

## 背景

### 问题分析

**文件验证的根本缺陷：**
1. L4→L3→L2 回退机制存在的原因就是方案文件可能不生成
2. 搜索"最新方案文件"可能找到错误的文件（不同上下文）
3. 文件存在 ≠ 技能被调用 ≠ 实际执行发生

**当前可用功能：**
- `enforcer.py` 已有技能追踪：`track_skill_call()`, `check_required_skills()`
- 执行追踪：`track_execution()` 支持 delegate_task, agent_pool_client, terminal
- 逃生舱：`MAX_ESCAPE_ATTEMPTS = 7` 防止无限循环
- 输出拦截：`OUTPUT_TOOLS` 在技能调用前阻止输出

**需要修复：**
- L4 仍尝试基于文件搜索授予执行认证（用户已删除此代码）
- `has_execution_auth()` 验证文件存在，而非技能使用
- L4→L3→L2 回退未在验证逻辑中正确处理

### 设计原则

1. **技能优先验证**: 检查技能是否被调用，而非文件是否存在
2. **执行验证**: 验证实际执行发生（delegate_task 等）
3. **优雅回退**: 逃生舱允许 L4→L3→L2 当技能不可用时
4. **无文件依赖**: 移除验证路径中所有基于文件的检查

---

## Task 1: 重构 has_execution_auth 支持技能验证

**Files:**
- Modify: `/home/kali/.hermes/plugins/soul-context-injector/interceptor.py:198-262`

**Step 1: 编写测试用例**

Create: `/home/kali/.hermes/plugins/soul-context-injector/test_skill_auth.py`

```python
"""测试技能验证认证"""
import os
import sys
import json
import tempfile
from pathlib import Path

# 添加插件目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from enforcer import create_tracker, track_skill_call, track_execution, cleanup_expired_trackers
from interceptor import has_execution_auth, get_auth_file


def test_l4_auth_via_skill_tracking():
    """L4: 技能调用 + 执行追踪 → 授予认证"""
    # 清理旧数据
    cleanup_expired_trackers()

    session_id = "test-l4-skill-auth"

    # 创建 L4 追踪器
    create_tracker(session_id, "L4")

    # 模拟技能调用
    track_skill_call(session_id, "planning-with-files")
    track_skill_call(session_id, "agent-pool")

    # 模拟执行
    track_execution(session_id, "delegate_task", "delegate_task")

    # 验证：应该有认证
    result = has_execution_auth(session_id)
    assert result == True, f"期望 True，实际 {result}"

    print("✅ 测试通过: L4 技能验证认证")


def test_l4_auth_missing_skill():
    """L4: 缺少技能 → 无认证"""
    session_id = "test-l4-missing-skill"

    create_tracker(session_id, "L4")
    # 只调用一个技能
    track_skill_call(session_id, "planning-with-files")
    # 没有执行

    result = has_execution_auth(session_id)
    assert result == False, f"期望 False，实际 {result}"

    print("✅ 测试通过: L4 缺少技能无认证")


def test_l3_auth_via_skill_tracking():
    """L3: 只需技能调用（无需执行追踪）"""
    session_id = "test-l3-skill-auth"

    create_tracker(session_id, "L3")
    track_skill_call(session_id, "deep-thinking")
    track_skill_call(session_id, "openclaw-behavior-plan")

    result = has_execution_auth(session_id)
    assert result == True, f"期望 True，实际 {result}"

    print("✅ 测试通过: L3 技能验证认证")


def test_l2_auth_via_skill_tracking():
    """L2: 只需技能调用"""
    session_id = "test-l2-skill-auth"

    create_tracker(session_id, "L2")
    track_skill_call(session_id, "deep-thinking")

    result = has_execution_auth(session_id)
    assert result == True, f"期望 True，实际 {result}"

    print("✅ 测试通过: L2 技能验证认证")


if __name__ == "__main__":
    test_l4_auth_via_skill_tracking()
    test_l4_auth_missing_skill()
    test_l3_auth_via_skill_tracking()
    test_l2_auth_via_skill_tracking()
    print("\n🎉 所有测试通过!")
```

**Step 2: 运行测试确认失败**

Run: `cd ~/.hermes/plugins/soul-context-injector && python test_skill_auth.py`
Expected: 测试失败（技能验证功能未实现）

**Step 3: 实现 has_execution_auth 技能验证**

Modify: `/home/kali/.hermes/plugins/soul-context-injector/interceptor.py`

在 `has_execution_auth()` 函数中添加技能验证路径：

```python
def has_execution_auth(session_id: str, expected_task: str = None) -> bool:
    """检查是否有有效的执行认证

    验证路径（按优先级）：
    1. Hermes approval 系统
    2. 本地认证文件（向后兼容）
    3. 技能调用追踪（新增）
    """
    # 方案1: Hermes approval 系统
    try:
        from tools.approval import get_current_session_key, is_approved
        session_key = get_current_session_key()
        if is_approved(session_key, "soul_execution_write"):
            logger.debug(f"[SOUL] 执行认证有效 (Hermes approval): {session_key}")
            return True
    except Exception as e:
        logger.debug(f"[SOUL] Hermes approval 检查失败: {e}")

    # 方案2: 本地认证文件
    auth_file = get_auth_file(session_id)
    if auth_file.exists():
        try:
            data = json.loads(auth_file.read_text())
            if data.get("session_id") != session_id:
                return False

            expires = datetime.datetime.fromisoformat(data["expires_at"])
            if datetime.datetime.now() > expires:
                return False

            logger.debug(f"[SOUL] 执行认证有效 (本地文件): {session_id}")
            return True
        except Exception as e:
            logger.warning(f"[SOUL] 执行认证检查失败: {e}")

    # 方案3: 技能调用追踪（新增）
    try:
        from .enforcer import get_tracker
        from .constants import SKILL_BINDINGS, REQUIRED_SKILLS_L4

        tracker = get_tracker(session_id)
        if tracker:
            task_level = tracker.get("task_level")
            called = tracker.get("called_skills", [])
            executed_by = tracker.get("executed_by", [])

            # L4: 检查技能调用 + 实际执行
            if task_level == "L4":
                required = REQUIRED_SKILLS_L4
                skills_ok = all(s in called for s in required)
                exec_ok = len(executed_by) > 0
                if skills_ok and exec_ok:
                    logger.debug(f"[SOUL] 执行认证有效 (技能追踪): skills={called}, execution={executed_by}")
                    return True

            # L2/L3: 只检查技能调用
            elif task_level in ["L2", "L3"]:
                required = SKILL_BINDINGS.get(task_level, [])
                if all(s in called for s in required):
                    logger.debug(f"[SOUL] 执行认证有效 (技能追踪): skills={called}")
                    return True
    except Exception as e:
        logger.debug(f"[SOUL] 技能追踪检查失败: {e}")

    return False
```

**Step 4: 运行测试确认通过**

Run: `cd ~/.hermes/plugins/soul-context-injector && python test_skill_auth.py`
Expected: 所有测试通过

**Step 5: 提交**

```bash
cd ~/.hermes/plugins/soul-context-injector
git add interceptor.py test_skill_auth.py
git commit -m "feat: add skill-based validation to has_execution_auth"
```

---

## Task 2: 在 pre_tool_call_hook 中授予技能验证认证

**Files:**
- Modify: `/home/kali/.hermes/plugins/soul-context-injector/__init__.py:156-181`

**Step 1: 编写测试**

Create: `/home/kali/.hermes/plugins/soul-context-injector/test_auto_auth.py`

```python
"""测试自动认证授予"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from enforcer import create_tracker, track_skill_call, track_execution, get_tracker
from interceptor import has_execution_auth, grant_execution_auth


def test_auto_auth_on_skill_and_execution():
    """L4: 技能调用 + 执行 → 自动授予认证"""
    session_id = "test-auto-auth"

    # 创建追踪器
    create_tracker(session_id, "L4")

    # 模拟技能调用
    track_skill_call(session_id, "planning-with-files")
    track_skill_call(session_id, "agent-pool")

    # 模拟执行
    track_execution(session_id, "delegate_task", "delegate_task")

    # 验证自动认证（通过 has_execution_auth 的方案3）
    result = has_execution_auth(session_id)
    assert result == True, f"期望自动认证 True，实际 {result}"

    print("✅ 测试通过: L4 自动认证授予")


if __name__ == "__main__":
    test_auto_auth_on_skill_and_execution()
    print("\n🎉 自动认证测试通过!")
```

**Step 2: 运行测试确认失败**

Run: `cd ~/.hermes/plugins/soul-context-injector && python test_auto_auth.py`
Expected: 测试通过（Task 1 已实现此功能）

**Step 3: 更新 L4 注释**

Modify: `/home/kali/.hermes/plugins/soul-context-injector/__init__.py`

更新 `pre_llm_call_hook()` 中的 L4 处理注释：

```python
# 2. L4 处理：等待技能调用
# 不再基于文件授予认证，而是基于技能调用追踪
# 认证授予见 has_execution_auth() 方案3
if task_level == "L4" and not workflow_name:
    logger.info(f"[SOUL] L4 任务，等待技能调用: {session_id}")
```

**Step 4: 提交**

```bash
cd ~/.hermes/plugins/soul-context-injector
git add __init__.py test_auto_auth.py
git commit -m "docs: update L4 handling comments for skill-based auth"
```

---

## Task 3: 增强 L4 指令添加回退指引

**Files:**
- Modify: `/home/kali/.hermes/plugins/soul-context-injector/context_builder.py:173-201`

**Step 1: 更新 L4 指令函数**

Modify: `/home/kali/.hermes/plugins/soul-context-injector/context_builder.py`

替换 `build_l4_explicit_directive()` 函数：

```python
def build_l4_explicit_directive(session_id: str) -> str:
    """构建 L4 执行指令（增强版 + 回退支持）"""
    return """【L4 执行方案 - 强制执行】

检测到方案执行任务，需要调用 planning-with-files + agent-pool 技能。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️  强制约束（必须严格遵守）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. 【第一步】你必须调用 skill_view(name="planning-with-files") 加载技能
2. 【第二步】你必须调用 skill_view(name="agent-pool") 加载技能
3. 【第三步】你必须使用以下方式之一执行任务：
   - delegate_task() 工具
   - agent_pool_client.execute() Python API
   - 终端: python ~/.hermes/skills/openclaw-imports/agent-pool/bin/agent-pool
4. 【禁止】未调用技能直接执行
5. 【禁止】未执行实际任务就输出结果

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 执行前验证清单
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

- [ ] 已调用 skill_view(name="planning-with-files")
- [ ] 已调用 skill_view(name="agent-pool")
- [ ] 已执行 delegate_task 或 agent_pool_client
- [ ] 已汇总结果到 progress.md

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔄 回退机制（L4 → L3 → L2）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

如果 agent-pool 不可用，按以下顺序回退：

**回退到 L3（方案生成）**：
1. 调用 skill_view(name="deep-thinking")
2. 调用 skill_view(name="openclaw-behavior-plan")
3. 生成 execution_plan.md
4. 等待用户确认

**回退到 L2（分析）**：
1. 调用 skill_view(name="deep-thinking")
2. 执行分析并输出结论

⚠️ 回退时在输出中说明：因 agent-pool 不可用，回退到 L3/L2

"""
```

**Step 2: 验证插件加载**

Run: `cd ~/.hermes && python -c "from plugins.soul_context_injector.context_builder import build_l4_explicit_directive; print(build_l4_explicit_directive('test')[:100])"`
Expected: 输出指令开头内容

**Step 3: 提交**

```bash
cd ~/.hermes/plugins/soul-context-injector
git add context_builder.py
git commit -m "feat: add L4 fallback guidance to L3/L2"
```

---

## Task 4: 更新错误消息添加回退选项

**Files:**
- Modify: `/home/kali/.hermes/plugins/soul-context-injector/enforcer.py:299-342`

**Step 1: 更新 check_required_skills 错误消息**

Modify: `/home/kali/.hermes/plugins/soul-context-injector/enforcer.py`

在 `check_required_skills()` 函数中更新错误消息：

```python
        error_text = "\n".join(error_parts)

        return False, f"""【规则违反】

{error_text}

当前任务等级: {task_level}
已调用技能: {', '.join(called) if called else '无'}
执行方式: {', '.join(executed_by) if executed_by else '无'}

---

【正确流程】

1. skill_view("planning-with-files")
2. skill_view("agent-pool")
3. delegate_task() 或 agent_pool_client.execute()
4. 输出结果

---

【回退选项】

如果 agent-pool 不可用：

**选项 A: 回退到 L3（生成方案）**
1. skill_view("deep-thinking")
2. skill_view("openclaw-behavior-plan")
3. 生成 execution_plan.md

**选项 B: 回退到 L2（仅分析）**
1. skill_view("deep-thinking")
2. 输出分析结论

---

【自动放行机制】

拦截次数: {escape_attempts}/{MAX_ESCAPE_ATTEMPTS}
达到 {MAX_ESCAPE_ATTEMPTS} 次后将自动放行（触发回退）

---

⚠️ 此拦截由 soul-context-injector 强制执行机制触发
"""
```

**Step 2: 验证插件加载**

Run: `cd ~/.hermes && python -c "from plugins.soul_context_injector.enforcer import check_required_skills; print('OK')"`
Expected: `OK`

**Step 3: 提交**

```bash
cd ~/.hermes/plugins/soul-context-injector
git add enforcer.py
git commit -m "feat: add fallback options to L4 error messages"
```

---

## Task 5: 清理废弃代码

**Files:**
- Modify: `/home/kali/.hermes/plugins/soul-context-injector/interceptor.py`

**Step 1: 添加废弃说明**

在 `interceptor.py` 文件开头添加废弃说明注释：

```python
"""
Soul Context Injector - 拦截逻辑

四层拦截 + 执行认证管理

废弃说明：
- find_execution_plan() 已移除，L4 验证改为基于技能调用
- has_execution_auth() 现在支持技能追踪验证（方案3）
"""
```

**Step 2: 确认无残留文件搜索代码**

Run: `cd ~/.hermes/plugins/soul-context-injector && grep -r "find_execution_plan" --include="*.py" || echo "无残留代码"`
Expected: `无残留代码`

**Step 3: 提交**

```bash
cd ~/.hermes/plugins/soul-context-injector
git add interceptor.py
git commit -m "docs: add deprecation notes for file-based validation"
```

---

## Task 6: 综合验证

**Step 1: 运行所有测试**

Run: `cd ~/.hermes/plugins/soul-context-injector && python -m pytest test_skill_auth.py test_auto_auth.py -v`
Expected: 所有测试通过

**Step 2: 验证无文件依赖**

Run: `cd ~/.hermes/plugins/soul-context-injector && grep -r "execution_plan" --include="*.py" | grep -v "# " | grep -v "deprecated" | grep -v "test_" || echo "✅ 无文件依赖残留"`
Expected: `✅ 无文件依赖残留`

**Step 3: 验证技能验证工作**

Run: `cd ~/.hermes/plugins/soul-context-injector && python -c "
from interceptor import has_execution_auth
from enforcer import create_tracker, track_skill_call, track_execution

# Create L4 tracker
create_tracker('verify-session', 'L4')

# Simulate skill calls
track_skill_call('verify-session', 'planning-with-files')
track_skill_call('verify-session', 'agent-pool')

# Simulate execution
track_execution('verify-session', 'delegate_task', 'delegate_task')

# Check auth
result = has_execution_auth('verify-session')
print(f'✅ 技能验证认证: {result}')
"`
Expected: `✅ 技能验证认证: True`

**Step 4: 最终提交**

```bash
cd ~/.hermes/plugins/soul-context-injector
git add -A
git commit -m "feat: complete skill-based validation refactor

- Replace file-based auth with skill tracking validation
- Add L4→L3→L2 fallback guidance
- Update error messages with fallback options
- Add comprehensive tests for skill auth
"
```

---

## 验证清单

完成所有任务后验证：

1. **单元测试:**
```bash
cd ~/.hermes/plugins/soul-context-injector
python test_skill_auth.py
python test_auto_auth.py
```

2. **集成测试:**
   - 在 Hermes 中创建 L4 任务
   - 验证技能追踪文件被创建
   - 尝试不调用技能直接输出
   - 应被拦截并显示清晰错误消息

3. **手动检查:**
   - `has_execution_auth()` 应支持技能验证
   - L4 指令应包含回退指引
   - 错误消息应包含回退选项

---

## 文件变更摘要

| 文件 | 变更 |
|------|------|
| `interceptor.py` | 重构 `has_execution_auth()` 支持技能验证 |
| `__init__.py` | 更新 L4 处理注释 |
| `context_builder.py` | 添加 L4 回退指引 |
| `enforcer.py` | 更新错误消息添加回退选项 |
| `test_skill_auth.py` | 新增技能验证测试 |
| `test_auto_auth.py` | 新增自动认证测试 |

---

## 设计总结

**改造前（基于文件）:**
```
L4 检测 → 搜索方案文件 → 找到则授予认证
问题：错误文件、无文件、过期文件
```

**改造后（基于技能）:**
```
L4 检测 → 创建追踪器 → 追踪技能调用 → 追踪执行 → 授予认证
回退：技能不可用 → 逃生舱 → 建议 L3/L2
```

**核心优势:**
1. 无文件依赖 - 即使方案未生成也能工作
2. 验证实际技能使用，而非文件存在
3. 优雅回退并提供清晰指引
4. 逃生舱防止无限循环
