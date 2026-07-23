# "你好" 被误判为 L3 根因分析

## 问题现象
用户输入"你好"，被误判为 L3 等级，触发了不必要的技能绑定。

## 根本原因

### 代码逻辑分析（analyzer.py 第214-296行）

`_classify_task()` 方法的判断顺序：

```
1. 工作流检测 → W
2. 确认词检测 → L4
3. 执行类关键词 → L3
4. 规划类关键词 → L2
5. 简单查询（TASK_KEYWORDS）→ L0/L1
6. 默认返回 → L2
```

### 判断路径追踪

输入："你好"

```
步骤1: 工作流检测 → 未命中
步骤2: 确认词检测 → 未命中（"你好"不在CONFIRM_KEYWORDS中）
步骤3: 执行类关键词 → 未命中
步骤4: 规划类关键词 → 未命中
步骤5: TASK_KEYWORDS 查询：
       L0: ["几点", "时间", "日期", "星期", "今天", ...] → 不包含"你好"
       L1: ["查看", "读取", "显示", ...] → 不包含"你好"
步骤6: 默认返回 → L2（保守判断）
```

**实际情况**：代码走到了步骤5，但在TASK_KEYWORDS中找不到"你好"，最终返回了**L2**而非L3。

## 为什么记忆中说是 L3？

可能的原因：
1. **Ollama 大模型路径**：本地降级规则返回L2后，可能还有Ollama分析路径介入
2. **用户主观感受**：用户看到触发了技能（如 deep-thinking），认为被判定为L3
3. **其他因素**：完整判断流程可能还有其他环节

## 真正的问题

### 问题1：TASK_KEYWORDS 缺失问候词

`TASK_KEYWORDS` 字典中**L0/L1都不包含问候词**：

```python
TASK_KEYWORDS = {
    "L0": ["几点", "时间", "日期", "星期", "今天", ...],  # 无问候词
    "L1": ["查看", "读取", "显示", ...],                 # 无问候词
}
```

### 问题2：双重检测机制不一致

代码中有**两处问候词检测**：

**位置1**：`_detect_skill_usage()` 方法（第315-317行）
```python
chat_keywords = ["你好", "嗨", "早上好", "晚上好", "hello", "hi", "怎么样"]
if any(kw in prompt.lower() for kw in chat_keywords) and len(prompt) < 20:
    return False  # 不使用技能
```

**位置2**：TASK_KEYWORDS 字典（第182-189行）
```python
"L0": ["几点", "时间", ...]  # 不包含问候词
"L1": ["查看", "读取", ...]  # 不包含问候词
```

**结果**：
- `_detect_skill_usage()` 正确识别为聊天，返回 False（不使用技能）
- `_classify_task()` 却因为没有匹配到L0/L1关键词，返回L2（保守判断）

### 问题3：默认保守策略不适合问候场景

```python
# 5. 默认保守判断 → L2（先分析，再决定是否执行）
return "L2"
```

这个默认策略适合**不确定的任务**，但对于**明确的问候**，应该返回L0。

## 修复方案

### 方案A：在 TASK_KEYWORDS 添加问候词（推荐）

```python
TASK_KEYWORDS = {
    "L0": ["几点", "时间", "日期", "星期", "今天", "明天", "昨天", "现在",
           "你好", "嗨", "早上好", "晚上好", "hello", "hi", "怎么样"],  # 添加问候词
    "L1": ["查看", "读取", "显示", "列出", "搜索", "查找", "获取", "看看", "浏览", "打开"],
}
```

**优点**：
- 修改最小
- 与现有逻辑一致
- 问候词直接匹配到L0

### 方案B：在 _classify_task 开头添加问候检测

```python
def _classify_task(self, prompt: str) -> str:
    lower = prompt.lower()
    
    # 0.5 问候检测（优先级最高）
    chat_keywords = ["你好", "嗨", "早上好", "晚上好", "hello", "hi", "怎么样"]
    if any(kw in lower for kw in chat_keywords) and len(prompt) < 20:
        return "L0"
    
    # 1. 工作流检测...
```

**优点**：
- 逻辑清晰
- 与 `_detect_skill_usage()` 一致

**缺点**：
- 代码重复（问候词定义两次）

### 方案C：统一问候词常量

```python
# 在文件顶部定义常量
CHAT_KEYWORDS = ["你好", "嗨", "早上好", "晚上好", "hello", "hi", "怎么样"]

# 在 TASK_KEYWORDS 中使用
TASK_KEYWORDS = {
    "L0": ["几点", "时间", ...] + CHAT_KEYWORDS,
}

# 在 _detect_skill_usage 中使用
if any(kw in prompt.lower() for kw in CHAT_KEYWORDS) and len(prompt) < 20:
    return False
```

**优点**：
- 单一数据源
- 易于维护
- 避免不一致

## 推荐方案

**方案A（最简单）**：直接在 TASK_KEYWORDS["L0"] 添加问候词。

理由：
1. 修改最小（只改一行）
2. 立即生效
3. 与现有逻辑完美兼容
4. 不引入新代码

## 验证方法

修改后测试：

```python
# 测试用例
test_cases = [
    ("你好", "L0"),
    ("嗨", "L0"),
    ("hello", "L0"),
    ("你好，今天怎么样", "L0"),  # 长度<20
    ("你好，我想问一个问题关于工作流的设计方案", "L3"),  # 包含"设计"关键词
]

for prompt, expected in test_cases:
    result = analyzer._classify_task(prompt)
    print(f"{prompt} → {result} (期望: {expected}) {'✓' if result == expected else '✗'}")
```

## 总结

| 维度 | 分析 |
|------|------|
| **根本原因** | TASK_KEYWORDS 缺失问候词 + 默认保守策略返回L2 |
| **为何误判** | "你好"未匹配任何关键词，走到默认返回L2 |
| **实际等级** | 应为L0（问候），却被判为L2（保守判断） |
| **修复方案** | 在TASK_KEYWORDS["L0"]添加问候词 |
| **修改范围** | 1行代码（第183行） |

## 额外发现

代码逻辑实际返回的是**L2**，不是L3。如果用户观察到触发了L3技能（如deep-thinking + openclaw-behavior-plan），说明：

1. **L2绑定的技能**：deep-thinking（USAGE.md第17行）
2. **用户可能混淆**：L2和L3都触发deep-thinking，区别是L3还触发openclaw-behavior-plan
3. **真正问题**：问候不应该触发任何技能，应该返回L0

这符合用户记忆中的"词汇理解陷阱"纠正 —— 不应该让问候词走到默认保守策略。
