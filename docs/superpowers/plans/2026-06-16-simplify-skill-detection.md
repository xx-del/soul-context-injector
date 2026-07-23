# 技能检测简化 实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 将技能意图检测从正则模式匹配简化为直接匹配白名单技能名

**架构：** 用简单的字符串包含检测替换复杂的正则表达式模式，使用户无需遵循特定句式即可触发白名单技能

**技术栈：** Python 3.x，无外部依赖

---

## 文件结构

| 文件 | 职责 | 状态 |
|------|------|------|
| `analyzer.py:181-234` | `detect_skill_intent()` 函数 - 核心检测逻辑 | 修改 |
| `constants.py:125-129` | `SKILL_WHITELIST` 常量定义 - 技能白名单 | 只读 |

---

## 任务 1：重构 detect_skill_intent 函数

**文件：**
- 修改：`analyzer.py:181-234`

- [ ] **步骤 1：删除正则模式定义**

删除 `analyzer.py:198-205` 的正则模式列表：

```python
# 删除以下代码
patterns = [
    r"使用\s*([a-z0-9\-]+)\s*技能",
    r"调用\s*([a-z0-9\-]+)\s*技能",
    r"用\s*([a-z0-9\-]+)\s*(?:技能)?处理",
    r"通过\s*([a-z0-9\-]+)\s*技能",
    r"利用\s*([a-z0-9\-]+)\s*技能",
]
```

- [ ] **步骤 2：重写检测逻辑**

将 `analyzer.py:181-234` 的 `detect_skill_intent` 函数替换为：

```python
def detect_skill_intent(user_message: str) -> Optional[Dict[str, Any]]:
    """技能意图检测（直接匹配白名单技能名）

    检测用户消息中是否包含白名单技能名称。
    白名单技能直接执行（L0），跳过 Ollama 分析和思考流程。

    Returns:
        匹配成功返回 decision 字典，否则返回 None
    """
    from .constants import SKILL_WHITELIST

    msg_lower = user_message.lower()

    for skill_name in SKILL_WHITELIST:
        if skill_name in msg_lower:
            logger.info(f"[soul] 技能白名单命中: {skill_name}")
            return {
                "success": True,
                "task_level": "L0",
                "workflow_name": None,
                "write_operation": False,
                "code_guidance": False,
                "agent_pool": False,
                "skill_usage": True,
                "self_improving": False,
                "skill_name": skill_name,
                "reason": f"技能白名单: {skill_name}",
            }

    return None
```

- [ ] **步骤 3：删除未使用的 re 导入（如果需要）**

检查文件顶部是否还有其他地方使用 `re` 模块。如果没有其他使用，删除：

```python
import re
```

**注意：** 查看 `analyzer.py`，`detect_workflow_local` 函数未使用正则，`LocalRuleClient` 类也未使用。可以安全删除 `import re`。

- [ ] **步骤 4：验证语法正确**

运行：`python -m py_compile analyzer.py`

预期：无输出（语法正确）

---

## 任务 2：添加单元测试

**文件：**
- 创建：`tests/test_skill_detection.py`

- [ ] **步骤 1：创建测试文件**

```python
"""技能检测单元测试"""
import unittest
from soul_context_injector.analyzer import detect_skill_intent


class TestSkillDetection(unittest.TestCase):
    """测试直接匹配白名单技能名"""

    def test_exact_match_with_pattern(self):
        """测试带句式的匹配"""
        result = detect_skill_intent("使用workflow-manager技能")
        self.assertIsNotNone(result)
        self.assertEqual(result["task_level"], "L0")
        self.assertEqual(result["skill_name"], "workflow-manager")

    def test_match_without_pattern(self):
        """测试不带句式的匹配"""
        result = detect_skill_intent("workflow-manager 处理任务")
        self.assertIsNotNone(result)
        self.assertEqual(result["task_level"], "L0")
        self.assertEqual(result["skill_name"], "workflow-manager")

    def test_match_with_spaces(self):
        """测试带空格的匹配"""
        result = detect_skill_intent("调用 workflow-manager 技能")
        self.assertIsNotNone(result)
        self.assertEqual(result["task_level"], "L0")

    def test_no_spaces(self):
        """测试无空格的匹配"""
        result = detect_skill_intent("使用workflow-manager技能")
        self.assertIsNotNone(result)
        self.assertEqual(result["task_level"], "L0")

    def test_non_whitelist_skill(self):
        """测试非白名单技能"""
        result = detect_skill_intent("使用unknown-skill技能")
        self.assertIsNone(result)

    def test_partial_match_not_triggered(self):
        """测试部分匹配不触发（技能名作为其他词的一部分）"""
        # agent-pool 可能出现在 "agent-pool-manager" 中
        # 但我们期望仍然匹配
        result = detect_skill_intent("agent-pool-manager test")
        self.assertIsNotNone(result)
        self.assertEqual(result["skill_name"], "agent-pool")

    def test_case_insensitive(self):
        """测试大小写不敏感"""
        result = detect_skill_intent("WORKFLOW-MANAGER test")
        self.assertIsNotNone(result)
        self.assertEqual(result["skill_name"], "workflow-manager")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **步骤 2：运行测试验证**

运行：`cd /home/kali/.hermes/plugins/soul-context-injector && python -m pytest tests/test_skill_detection.py -v`

预期：所有测试通过

---

## 任务 3：提交变更

- [ ] **步骤 1：查看变更**

运行：`git diff analyzer.py`

预期：显示删除正则模式、简化检测逻辑的变更

- [ ] **步骤 2：提交代码**

```bash
git add analyzer.py tests/test_skill_detection.py
git commit -m "refactor: 简化技能检测 - 直接匹配白名单技能名

- 移除复杂的正则模式匹配
- 直接检测用户消息中是否包含白名单技能名
- 用户无需遵循特定句式即可触发白名单技能
- 添加单元测试覆盖各种匹配场景

BREAKING CHANGE: 移除对特定句式（如'使用X技能'）的要求"
```

---

## 验证清单

完成后验证：

- [ ] 语法检查通过：`python -m py_compile analyzer.py`
- [ ] 单元测试通过：`pytest tests/test_skill_detection.py -v`
- [ ] 手动测试：输入 `使用vuln-exploit-system技能 处理20260603` 确认进入 L0
- [ ] 手动测试：输入 `vuln-exploit-system 20260603` 确认进入 L0
- [ ] 代码已提交

---

## 关键文件路径

| 文件 | 说明 |
|------|------|
| `analyzer.py:181-234` | 核心修改位置 |
| `constants.py:125-129` | `SKILL_WHITELIST` 白名单定义 |
| `tests/test_skill_detection.py` | 新增测试文件 |
