# Ollama 提示词语义版恢复 + LocalRuleClient 补强 实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 将 soul-context-injector 的 Ollama 提示词从当前 v12.0 关键词规则版恢复为 v11.0 语义判断版，同时补强 LocalRuleClient 的关键词覆盖和优先级逻辑，缩小两类场景的覆盖率差距。

**架构：** 三处改动——①替换 `prompts/ollama_prompt.md` 为语义版；②增强 `analyzer.py` 的 LocalRuleClient 关键词表和优先级逻辑；③恢复 `context_builder.py` 的 phase_context 注入（含新增 `get_workflow_names()` 辅助函数）。所有改动均有测试先行（TDD）。

**技术栈：** Python 3.13, pytest, Qwen2.5-7B (Ollama), soul-context-injector 插件框架

---

## 文件结构

### 修改的文件

| 文件 | 职责 | 改动类型 |
|------|------|---------|
| `prompts/ollama_prompt.md` | Ollama 任务分析提示词 | **替换内容** — 从 v12.0 关键词版 → v11.0 语义版 |
| `analyzer.py` | LocalRuleClient 关键词表和优先级逻辑 | **局部修改** — 扩充关键词 + 调整 L1/L2 优先级 |
| `context_builder.py` | phase_context 注入（工作流名/pending 方案） | **局部修改** — 恢复注释代码 + 新增 `get_workflow_names()` |

### 新建的测试文件

| 文件 | 职责 |
|------|------|
| `tests/test_local_rule_coverage.py` | 测试 LocalRuleClient 对边界场景的分类准确率 |
| `tests/test_ollama_prompt_integration.py` | 集成测试：用实际 Ollama 验证语义版提示词输出 |
| `tests/test_analyze_task_coverage.py` | 测试 `analyze_task()` 全管线的端到端分类 |

---

## 改动详解

### 一、LocalRuleClient 关键词补强（analyzer.py）

**当前缺口分析**（来自实测）：

| 消息 | 预期 | 当前结果 | 根因 |
|------|------|---------|------|
| "查看日志找出问题" | L2 | L1 | "找出"不在 L2/planning 词表 |
| "查询天气并分析" | L2 | L1 | L1关键词先于L2检查 |
| "修复bug" | L3 | L2 | "修复"不在 exec_kws |
| "实现功能" | L3 | L2 | "实现"不在 exec_kws |
| "You should fix this issue" | L3 | L2 | "fix"不在 exec_kws |
| "我看一下这个对不对" | L2 | L1 | "看一下"不在 L2 词表 |
| "Create a new file" | L3 | L1→保守L2 | "create"不在词表 |
| "同意后执行" | 非L4 | 误判L4 | 无排除逻辑 |

**改动 A：扩充 exec_kws（L3，第 2 步）**

追加到 `exec_kws` 列表：
```
修复, 实现, 改造, 构建, 生成, 替换, 迁移,
fix, implement, create, build, generate, replace, migrate
```

**改动 B：扩充 planning_kws（L2，第 3 步，高于 L1）**

追加到 `planning_kws` 列表：
```
找出, 检查, 验证, 排查, 核对, 处理, 定位,
analyze, check, find, verify, debug, review
```

**改动 C：TASK_KEYWORDS["L2"] 追加**

```
看一下, read, what, how
```

**改动 D：调整优先级顺序**

当前 `_classify_task()` 中第 4 步的迭代：
```python
# 4. 简单查询 → 匹配关键词表
for level, keywords in self.TASK_KEYWORDS.items():
    if any(kw in lower for kw in keywords):
        return level
```
`TASK_KEYWORDS` 的 dict 顺序是 L0→L1→L2→L3。如果一条消息同时命中了 L1 和 L2 的关键词，会先命中 L1 返回错误结果。

**修复方案**：将迭代顺序改为先查 L2 再查 L1（L0 和 L3 按原顺序）：
```python
# 4. 简单查询 → 匹配关键词表（优先检查分析类 L2，再查查询类 L1）
level_order = ["L2", "L1", "L0", "L3"]
for level in level_order:
    keywords = self.TASK_KEYWORDS.get(level, [])
    if any(kw in lower for kw in keywords):
        return level
```

**改动 E：纯确认词排除 "同意后执行" 模式**

在 `_classify_task()` 第 1 步（确认词检测）中，增加排除模式：
```python
confirm_then_exec_patterns = [
    "同意后执行", "同意后实施", "同意后部署",
    "确认后执行", "确认后实施",
    "批准后执行", "批准后实施",
]
```

### 二、提示词替换（ollama_prompt.md）

将整个文件内容替换为 v11.0 语义版（源自 `ollama_prompt.md.0514`），核心方法从"包含X则判Y"改为"语义三问分析"。主要变化：

- 移除全部关键词枚举规则
- 增加"语义判断三问"框架（想要什么？改变什么？多复杂？）
- 增加"多动词优先级规则"（分析>执行>查询）
- 增加 L4 五步判断法（含"同意后执行"排除）
- 增加边界示例和正反案例
- 遵循现有 JSON 输出格式，无需后端代码调整

### 三、恢复 phase_context 注入（context_builder.py）

**当前状态**：`build_ollama_prompt()` 中的 phase_context 注入代码被注释掉。

**改动**：
1. 在 `analyzer.py` 中新增 `get_workflow_names()` 函数（从 `_index.yaml` 读取活跃工作流名称列表）
2. 恢复 `context_builder.py` 中的注释代码，注入工作流名称和 pending 方案状态

注意：原注释中提到的 `find_execution_plan()` 已不存在，这部分跳过。仅恢复工作流名称注入。

---

## 任务结构

### 任务 1：为 LocalRuleClient 写覆盖率测试（TDD，测试先行）

**文件：**
- 创建：`tests/test_local_rule_coverage.py`
- 不修改生产文件

- [ ] **步骤 1：编写测试——边界场景分类**

创建测试文件，覆盖以下边界场景：

```python
"""测试 LocalRuleClient 的边界场景覆盖率"""
import sys
from pathlib import Path

PLUGIN_DIR = Path(__file__).parent.parent.resolve()

# 确保测试 conftest 已加载合成包
pytest_plugins = ["tests.conftest"]


class TestLocalRuleCoverage:
    """覆盖本地规则在关键词匹配上的已知缺口"""

    def _make_client(self):
        """创建 LocalRuleClient 实例（跳过 import 障碍）"""
        sys.path.insert(0, str(PLUGIN_DIR))
        from analyzer import local_client
        return local_client

    # === L2 边界：多动词优先级 ===

    def test_l2_find_problem_in_logs(self):
        """"查看日志找出问题" → L2（"找出"隐含分析意图）"""
        client = self._make_client()
        result = client.analyze("查看日志找出问题")
        assert result["task_level"] == "L2", (
            f"预期 L2，实际 {result['task_level']}"
        )

    def test_l2_query_and_analyze(self):
        """"查询天气并分析" → L2（"分析"语义优先于"查询"）"""
        client = self._make_client()
        result = client.analyze("查询天气并分析")
        assert result["task_level"] == "L2", (
            f"预期 L2，实际 {result['task_level']}"
        )

    def test_l2_check_if_correct(self):
        """"我看一下这个对不对" → L2（隐含判断需求）"""
        client = self._make_client()
        result = client.analyze("我看一下这个对不对")
        assert result["task_level"] == "L2", (
            f"预期 L2，实际 {result['task_level']}"
        )

    def test_l2_search_then_report(self):
        """"搜索完暂停生成报告" → L2（复合分析任务）"""
        client = self._make_client()
        result = client.analyze("搜索完毕之后暂停 生成报告 再进行下一步")
        assert result["task_level"] == "L2", (
            f"预期 L2，实际 {result['task_level']}"
        )

    def test_l2_how_to(self):
        """"如何实现这个功能" → L2（"如何"隐含分析）"""
        client = self._make_client()
        result = client.analyze("如何实现这个功能")
        assert result["task_level"] == "L2", (
            f"预期 L2，实际 {result['task_level']}"
        )

    def test_l2_what_is_this(self):
        """"what is this function" → L2（英文分析意图）"""
        client = self._make_client()
        result = client.analyze("what is this function")
        assert result["task_level"] == "L2", (
            f"预期 L2，实际 {result['task_level']}"
        )

    # === L3 边界：执行意图 ===

    def test_l3_fix_bug(self):
        """"修复bug" → L3（执行意图）"""
        client = self._make_client()
        result = client.analyze("修复bug")
        assert result["task_level"] == "L3", (
            f"预期 L3，实际 {result['task_level']}"
        )

    def test_l3_implement_feature(self):
        """"实现功能" → L3（执行意图）"""
        client = self._make_client()
        result = client.analyze("实现功能")
        assert result["task_level"] == "L3", (
            f"预期 L3，实际 {result['task_level']}"
        )

    def test_l3_english_fix(self):
        """"fix this issue" → L3（英文执行意图）"""
        client = self._make_client()
        result = client.analyze("fix this issue")
        assert result["task_level"] == "L3", (
            f"预期 L3，实际 {result['task_level']}"
        )

    def test_l3_create_file(self):
        """"Create a new config file" → L3（英文创建）"""
        client = self._make_client()
        result = client.analyze("Create a new config file")
        assert result["task_level"] == "L3", (
            f"预期 L3，实际 {result['task_level']}"
        )

    # === L4 边界 ===

    def test_l4_pure_confirm(self):
        """"确认" → L4（纯确认词）"""
        client = self._make_client()
        result = client.analyze("确认")
        assert result["task_level"] == "L4", (
            f"预期 L4，实际 {result['task_level']}"
        )

    def test_not_l4_confirm_then_exec(self):
        """"同意后执行" → 非L4（描述执行方式）"""
        client = self._make_client()
        result = client.analyze("同意后执行")
        assert result["task_level"] != "L4", (
            f"预期非L4，实际 {result['task_level']}"
        )

    # === L1 正常场景 保回归 ===

    def test_l1_view_file(self):
        """"查看这个文件" → L1"""
        client = self._make_client()
        result = client.analyze("查看这个文件")
        assert result["task_level"] == "L1"

    def test_l1_search(self):
        """"搜索 TODO" → L1"""
        client = self._make_client()
        result = client.analyze("搜索 TODO")
        assert result["task_level"] == "L1"
```

- [ ] **步骤 2：运行测试确认失败**

```bash
cd ~/.hermes/plugins/soul-context-injector
python3 -m pytest tests/test_local_rule_coverage.py -v
```

预期：12 个测试中约 8-10 个 FAIL（当前代码未处理这些边界）。

- [ ] **步骤 3：实现 LocalRuleClient 关键词扩充 + 优先级调整**

在 `analyzer.py` 中执行以下 5 处改动：

**改动 3.1**：扩充 `exec_kws`：
```python
exec_kws = ["创建", "实施", "执行", "部署", "安装", "卸载", "修改", "删除", "写入",
            "create", "implement", "deploy",
            "修复", "实现", "改造", "构建", "生成", "替换", "迁移",
            "fix", "implement", "create", "build", "generate", "replace", "migrate"]
```

**改动 3.2**：扩充 `planning_kws`：
```python
planning_kws = ["制定方案", "规划", "分析", "评估", "设计", "生成计划", "写方案", "帮我做",
                "找出", "检查", "验证", "排查", "核对", "处理", "定位",
                "analyze", "check", "find", "verify", "debug", "review"]
```

**改动 3.3**：扩充 `TASK_KEYWORDS["L2"]`：
```python
"L2": [
    "分析", "比较", "评估", "设计", "优化", "思考", "为什么", "怎么",
    "制定", "规划", "方案", "研究", "探讨", "推导", "计算", "总结",
    "判断", "诊断", "解析", "理解", "归纳", "对比", "改进", "建议",
    "看一下", "read", "what", "how"
]
```

**改动 3.4**：在确认词检测第一步增加"同意后执行"排除模式：
```python
# 1. 确认词检测（优化后）
if any(kw in lower for kw in CONFIRM_KEYWORDS):
    
    # 步骤1.1: 排除"同意后执行"模式
    confirm_then_exec_patterns = [
        "同意后执行", "同意后实施", "同意后部署",
        "确认后执行", "确认后实施", "确认后部署",
        "批准后执行", "批准后实施",
        "我同意后执行", "我确认后执行",
    ]
    has_confirm_then_exec = any(p in lower for p in confirm_then_exec_patterns)
    
    if not has_confirm_then_exec:
        # 后续确认词判断逻辑不变...
```

**改动 3.5**：调整 TASK_KEYWORDS 迭代顺序——先查 L2 再查 L1：

将第 4 步从：
```python
for level, keywords in self.TASK_KEYWORDS.items():
    if any(kw in lower for kw in keywords):
        return level
```
改为：
```python
# 优先检查分析类 L2，再查查询类 L1
priority_order = ["L2", "L0", "L1", "L3"]
for level in priority_order:
    keywords = self.TASK_KEYWORDS.get(level, [])
    if any(kw in lower for kw in keywords):
        return level
```

- [ ] **步骤 4：运行测试验证通过**

```bash
cd ~/.hermes/plugins/soul-context-injector
python3 -m pytest tests/test_local_rule_coverage.py -v
```

预期：全部 PASS。如果仍有 FAIL，检查是否遗漏了某个关键词或逻辑。

- [ ] **步骤 5：运行回归测试**

```bash
cd ~/.hermes/plugins/soul-context-injector
python3 -m pytest tests/ -v
```

预期：原有 7 个测试仍然 PASS，无回归。


- [ ] **步骤 6：Commit**

```bash
cd ~/.hermes/plugins/soul-context-injector
git -C /home/kali/.hermes add plugins/soul-context-injector/analyzer.py
git -C /home/kali/.hermes add plugins/soul-context-injector/tests/test_local_rule_coverage.py
git -C /home/kali/.hermes commit -m "fix(soul): expand LocalRuleClient keywords and fix L1/L2 priority

- Add '找出/修复/实现/fix/create' etc. to LocalRuleClient keywords
- Fix L1 vs L2 priority: analyze keywords checked before query keywords
- Add '同意后执行' exclusion pattern for L4 confirmation
- 12 new test cases covering known classification gaps
"
```


### 任务 2：替换 Ollama 提示词为语义版

**文件：**
- 修改：`prompts/ollama_prompt.md`

- [ ] **步骤 1：编写测试——Ollama 语义版输出验证（集成测试）**

创建 `tests/test_ollama_prompt_integration.py`：

```python
"""集成测试：验证实际 Ollama 在语义版 prompt 下的输出"""
import json
import urllib.request
import pytest
from pathlib import Path

PLUGIN_DIR = Path(__file__).parent.parent.resolve()

# 从 config.yaml 读取配置
import yaml
config_path = Path.home() / ".hermes" / "config.yaml"
with open(config_path) as f:
    config = yaml.safe_load(f)
soul_config = config.get("plugins", {}).get("soul-context-injector", {})
OLLAMA_URL = soul_config.get("ollama_url", "http://localhost:11434/api/generate")
OLLAMA_MODEL = soul_config.get("ollama_model", "qcwind/qwen2.5-7B-instruct-Q4_K_M:latest")


def _call_ollama(prompt_text: str, user_msg: str) -> dict:
    """模拟 call_ollama() 的调用方式"""
    full_prompt = f"{prompt_text}\n\n## 用户消息\n{user_msg}"
    payload = json.dumps({
        "model": OLLAMA_MODEL,
        "prompt": full_prompt,
        "stream": False,
        "options": {"num_ctx": 12288}
    }).encode()
    req = urllib.request.Request(OLLAMA_URL, payload, {"Content-Type": "application/json"})
    resp = json.loads(urllib.request.urlopen(req, timeout=15).read())
    return resp


def _extract_json(text: str) -> dict:
    """从模型输出中提取 JSON（与 parse_decision() 逻辑一致）"""
    js = text.find("{")
    je = text.rfind("}") + 1
    if js >= 0 and je > js:
        try:
            return json.loads(text[js:je])
        except json.JSONDecodeError:
            pass
    return {}


class TestOllamaSemanticPrompt:
    """验证语义版提示词下 Ollama 输出的格式和分类质量"""

    PROMPT_CONTENT = None  # 运行时从文件加载

    @classmethod
    def setup_class(cls):
        prompt_path = PLUGIN_DIR / "prompts" / "ollama_prompt.md"
        assert prompt_path.exists(), "提示词文件不存在"
        cls.PROMPT_CONTENT = prompt_path.read_text(encoding="utf-8")

    def _analyze(self, msg: str) -> dict:
        """直接调用 Ollama 并解析 JSON 结果"""
        assert self.PROMPT_CONTENT, "提示词未加载"
        resp = _call_ollama(self.PROMPT_CONTENT, msg)
        text = resp.get("response", "")
        parsed = _extract_json(text)
        return parsed

    # === 格式验证 ===

    def test_json_format_valid(self):
        """验证 Ollama 返回的 JSON 包含所有必需字段"""
        result = self._analyze("今天天气怎么样")
        required = {"task_level", "workflow_name", "write_operation",
                    "code_guidance", "agent_pool", "self_improving"}
        assert required.issubset(result.keys()), (
            f"缺失字段: {required - set(result.keys())}"
        )

    def test_task_level_in_valid_range(self):
        """task_level 必须是 L0/L1/L2/L3/L4 之一"""
        result = self._analyze("查看文件")
        assert result.get("task_level") in ("L0", "L1", "L2", "L3", "L4"), (
            f"无效 task_level: {result.get('task_level')}"
        )

    # === 分类验证 ===

    def test_simple_query_l1(self):
        """"查看文件内容" → L1"""
        result = self._analyze("查看文件内容")
        assert result.get("task_level") == "L1"

    def test_analysis_query_l2(self):
        """"分析系统架构" → L2"""
        result = self._analyze("分析系统架构")
        assert result.get("task_level") == "L2"

    def test_execute_query_l3(self):
        """"创建配置文件" → L3"""
        result = self._analyze("创建配置文件")
        assert result.get("task_level") == "L3"

    def test_multi_verb_priority(self):
        """"查看日志找出问题" → L2（语义版应理解"找出"的分析意图）"""
        result = self._analyze("查看日志找出问题")
        assert result.get("task_level") == "L2", (
            f"语义版应识别'找出'的分析意图，实际: {result.get('task_level')}"
        )

    def test_english_fix_l3(self):
        """"fix this bug" → L3"""
        result = self._analyze("fix this bug")
        assert result.get("task_level") == "L3", (
            f"语义版应识别英文执行意图，实际: {result.get('task_level')}"
        )
```

- [ ] **步骤 2：运行测试确认失败（用当前 v12.0 关键词版）**

```bash
cd ~/.hermes/plugins/soul-context-injector
# 先确认当前提示词是关键词版
head -3 prompts/ollama_prompt.md
# 跑测试
python3 -m pytest tests/test_ollama_prompt_integration.py -v
```

预期：约 2-3 个 FAIL，主要是 multi_verb_priority 和 english_fix。

- [ ] **步骤 3：替换提示词文件内容**

将 `prompts/ollama_prompt.md` 替换为 v11.0 语义版内容（从 `prompts/ollama_prompt.md.0514` 获取，保留 `{user_message}` 和 `{phase_context}` 占位符）。

内容要点：
- 标题改为 `# Ollama 任务分析提示词 v11.0 - 语义判断版`
- 保留 `{phase_context}` 和 `{user_message}` 占位符
- 核心方法改为"语义判断三问"
- 增加"多动词优先级规则"
- 增加 L4 五步判断法
- 增加正反边界案例
- 输出格式保持不变（确保 `parse_decision()` 兼容）
- **增加关键约束**：在输出格式区显式声明：
  > "**重要约束**：无论消息多么模糊，你都必须输出 JSON，禁止拒绝回答。"

- [ ] **步骤 4：运行测试验证通过**

```bash
cd ~/.hermes/plugins/soul-context-injector
python3 -m pytest tests/test_ollama_prompt_integration.py -v
```

预期：全部 PASS。如果 multi_verb_priority 仍有问题，分析原因是 prompt 措辞不够明确，微调后重跑。

- [ ] **步骤 5：运行回归测试**

```bash
cd ~/.hermes/plugins/soul-context-injector
python3 -m pytest tests/ -v
```

预期：全部 PASS。

- [ ] **步骤 6：Commit**

```bash
cd ~/.hermes/plugins/soul-context-injector
git -C /home/kali/.hermes add prompts/ollama_prompt.md
git -C /home/kali/.hermes add tests/test_ollama_prompt_integration.py
git -C /home/kali/.hermes commit -m "fix(soul): restore v11.0 semantic analysis prompt

- Replace v12.0 keyword-based Ollama prompt with v11.0 semantic version
- Core method: 'semantic three-question analysis' instead of keyword matching
- Adds multi-verb priority rules (analyze > execute > query)
- Adds L4 five-step judgment with '同意后执行' exclusion
- Prevents model refusal with explicit output constraints
"
```


### 任务 3：恢复 phase_context 注入

**文件：**
- 修改：`analyzer.py` — 新增 `get_workflow_names()` 函数
- 修改：`context_builder.py` — 恢复 phase_context 注入

- [ ] **步骤 1：编写测试——phase_context 注入验证**

创建 `tests/test_phase_context_injection.py`（或在 `test_context_builder_directives.py` 中新增）：

```python
"""测试 phase_context 在 Ollama prompt 中的注入"""

from pathlib import Path
from unittest.mock import patch

PLUGIN_DIR = Path(__file__).parent.parent.resolve()


def test_phase_context_contains_workflow_names():
    """验证 phase_context 包含工作流名称（如已有活跃工作流）"""
    import sys
    sys.path.insert(0, str(PLUGIN_DIR))
    from context_builder import build_ollama_prompt
    
    # 调用时注入任意用户消息
    result = build_ollama_prompt("查看文件")
    
    # 如果存在活跃工作流，phase_context 应包含工作流列表
    # 如果不存在，phase_context 应为空
    assert isinstance(result, str)
    assert len(result) > 100  # 应有足够的提示词长度
    assert "{user_message}" not in result  # 占位符已被替换
```

- [ ] **步骤 2：运行测试确认失败**

```bash
cd ~/.hermes/plugins/soul-context-injector
python3 -m pytest tests/test_phase_context_injection.py -v
```

预期：FAIL 或出现 import 错误（需要新增函数后才能通过）。

- [ ] **步骤 3：实现改动**

**改动 3.1**：在 `analyzer.py` 中新增 `get_workflow_names()` 函数：

在 `detect_workflow_local()` 函数附近新增：

```python
def get_workflow_names() -> list:
    """获取所有活跃工作流名称列表"""
    workflows_dir = Path.home() / ".hermes" / "workflows"
    index_path = workflows_dir / "_index.yaml"
    
    if not index_path.exists():
        return []
    
    try:
        import yaml
        with open(index_path, 'r', encoding='utf-8') as f:
            index = yaml.safe_load(f)
        
        if not index or 'workflows' not in index:
            return []
        
        names = []
        for wf in index.get('workflows', []):
            if wf.get('status') == 'active':
                name = wf.get('name', '')
                if name:
                    names.append(name)
        return names
    except Exception as e:
        logger.warning(f"[soul] 获取工作流名称失败: {e}")
        return []
```

**改动 3.2**：在 `context_builder.py` 的 `build_ollama_prompt()` 中恢复 phase_context 注入：

取消注释第 457-468 行的代码（工作流名称注入部分），将 `from .analyzer import get_workflow_names` 改为正确导入。pending 方案注入部分（第 474-481 行）因 `find_execution_plan()` 已删除，跳过恢复。

```python
# 构建 phase_context
phase_context_parts = []

# 1. 注入活跃工作流名称（用于精确匹配）
try:
    from .analyzer import get_workflow_names
    workflow_names = get_workflow_names()
    if workflow_names:
        phase_context_parts.append("## 工作流名称列表（用于精确匹配）\n")
        phase_context_parts.append("如果用户消息完全匹配以下任一名称，则 workflow_name 填写该名称，task_level 填写 \"L1\"。\n\n")
        for name in workflow_names[:20]:
            phase_context_parts.append(f"- {name}\n")
        phase_context_parts.append("\n")
except Exception as e:
    logger.warning(f"[soul] 获取工作流名称失败: {e}")

phase_context = "".join(phase_context_parts) if phase_context_parts else ""
```

- [ ] **步骤 4：运行测试验证通过**

```bash
cd ~/.hermes/plugins/soul-context-injector
python3 -m pytest tests/test_phase_context_injection.py tests/test_context_builder_directives.py -v
```

预期：全部 PASS。

- [ ] **步骤 5：运行全回归测试**

```bash
cd ~/.hermes/plugins/soul-context-injector
python3 -m pytest tests/ -v
```

预期：全部 PASS。

- [ ] **步骤 6：Commit**

```bash
cd ~/.hermes/plugins/soul-context-injector
git -C /home/kali/.hermes add analyzer.py context_builder.py
git -C /home/kali/.hermes add tests/test_phase_context_injection.py
git -C /home/kali/.hermes commit -m "feat(soul): restore phase_context injection for Ollama prompt

- Add get_workflow_names() to analyzer.py for reading active workflow list
- Restore commented phase_context injection in context_builder.py
- Injects workflow names into Ollama prompt for accurate matching
"
```


### 任务 4：端到端管线覆盖率测试

**文件：**
- 创建：`tests/test_analyze_task_coverage.py`

- [ ] **步骤 1：编写测试——analyze_task 全管线覆盖**

```python
"""测试 analyze_task() 全管线的端到端分类"""
import sys
from pathlib import Path
from unittest.mock import patch

PLUGIN_DIR = Path(__file__).parent.parent.resolve()


class TestAnalyzeTaskCoverage:
    """覆盖已知的边界场景，验证 analyze_task 全管线的行为"""

    def _call_analyze(self, message: str) -> dict:
        sys.path.insert(0, str(PLUGIN_DIR))
        from analyzer import analyze_task
        
        # 使用 patch 阻止实际 Ollama 调用（确保走本地规则路径）
        with patch("analyzer.call_ollama_with_retry", return_value=None):
            with patch("analyzer.call_ollama", return_value=None):
                result = analyze_task(message)
        return result

    def test_l2_find_problem(self):
        """多动词：查看日志找出问题 → L2"""
        r = self._call_analyze("查看日志找出问题")
        assert r["task_level"] == "L2", f"预期L2，实际 {r['task_level']}"

    def test_l3_fix_bug(self):
        r = self._call_analyze("修复bug")
        assert r["task_level"] == "L3", f"预期L3，实际 {r['task_level']}"

    def test_l3_implement(self):
        r = self._call_analyze("实现一个功能")
        assert r["task_level"] == "L3", f"预期L3，实际 {r['task_level']}"

    def test_not_l4_confirm_and_exec(self):
        r = self._call_analyze("同意后执行")
        assert r["task_level"] != "L4", f"预期非L4，实际 {r['task_level']}"

    def test_l4_pure_confirm(self):
        r = self._call_analyze("确认")
        assert r["task_level"] == "L4", f"预期L4，实际 {r['task_level']}"

    def test_l2_english_what(self):
        r = self._call_analyze("what does this function do")
        assert r["task_level"] == "L2", f"预期L2，实际 {r['task_level']}"

    def test_l3_english_fix(self):
        r = self._call_analyze("fix the bug in this code")
        assert r["task_level"] == "L3", f"预期L3，实际 {r['task_level']}"
```

- [ ] **步骤 2：运行测试验证通过**

```bash
cd ~/.hermes/plugins/soul-context-injector
python3 -m pytest tests/test_analyze_task_coverage.py -v
```

预期：全部 PASS（依赖任务1和任务3的改动）。

- [ ] **步骤 3：运行全回归测试**

```bash
cd ~/.hermes/plugins/soul-context-injector
python3 -m pytest tests/ -v
```

预期：全部 PASS（含原有7个 + 新增约20+个）。

- [ ] **步骤 4：Commit**

```bash
cd ~/.hermes/plugins/soul-context-injector
git -C /home/kali/.hermes add tests/test_analyze_task_coverage.py
git -C /home/kali/.hermes commit -m "test(soul): add end-to-end coverage test for analyze_task

- 7 test cases covering multi-verb priority, L3 keywords, L4 edge cases, English support
- Uses mocked Ollama to force local rule path
- Verifies full pipeline classification behavior
"
```

---

## 自检

### 1. 规格覆盖度

| 需求 | 对应任务 |
|------|---------|
| 补充 LocalRuleClient 关键词表 | 任务 1 (改动 3.1-3.3) |
| 调整 L1/L2 优先级顺序 | 任务 1 (改动 3.5) |
| 加入"同意后执行"排除逻辑 | 任务 1 (改动 3.4) |
| 替换 Ollama 提示词为语义版 | 任务 2 |
| 恢复 phase_context 注入 | 任务 3 |
| 新增 get_workflow_names() | 任务 3 (改动 3.1) |
| TDD 测试覆盖边界场景 | 任务 1/2/3/4 各自的 Step 1 |
| 全回归测试 | 任务 1-4 各自的回归步骤 |

### 2. 占位符扫描

- 每个步骤都有完整代码，无"待定"、"TODO"、"后续实现"
- 测试用例都有具体断言逻辑
- 命令都有精确的命令行调用

### 3. 类型一致性

- `get_workflow_names()` 签名和返回值在 analyzer.py 定义，在 context_builder.py 中调用，类型一致
- `LocalRuleClient.analyze()` 签名字返回 dict 未变，兼容下游调用
- `parse_decision()` 解析逻辑未变，兼容新旧 prompt 输出格式

---

## 执行交接

计划已完成并保存到 `~/.hermes/plugins/soul-context-injector/docs/plans/2026-07-28-ollama-prompt-semantic-restore.md`。两种执行方式：

**1. 子代理驱动（推荐）** — 每个任务调度一个新的子代理，任务间审查，快速迭代

**2. 内联执行** — 在当前会话中使用 executing-plans 执行任务，批量执行并设有检查点

选哪种方式？
