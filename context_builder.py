"""
Soul Context Injector - 上下文构建

构建注入到 LLM 的上下文内容
"""

import json
from typing import Dict, Any, List, Optional
from pathlib import Path

from .constants import (
    logger,
    PLUGIN_DIR,
    RULES_DIR,
)
from .analyzer import load_rules


# ============ 技能绑定映射 ============

SKILL_BINDINGS = {
    "L2": ["deep-thinking"],
    "L3": ["deep-thinking", "openclaw-behavior-plan"],
    "L4": ["planning-with-files", "agent-pool"],
}


def get_bound_skills(task_level: str) -> List[str]:
    """获取任务等级对应的绑定技能"""
    return SKILL_BINDINGS.get(task_level, [])


# ============ 工作流执行指令 ============

def build_workflow_directive(workflow_name: str) -> str:
    """构建工作流执行指令
    
    工作流是标准化流程，不需要规则注入
    """
    return f"""【工作流执行指令】

检测到工作流任务：{workflow_name}

此任务是自动化流程，直接执行，不需要方案确认。

### 执行流程

1. 调用 `skill_view(name="workflow-manager")` 加载技能
2. 调用技能执行工作流：`{workflow_name}`
3. 验证每步执行结果
4. 汇总所有步骤结果后输出「执行完成」

### 约束

- ✅ 直接执行，不需要方案确认
- ✅ 必须验证每个步骤的输出
- ✅ 所有步骤完成后才能输出「执行完成」
- ❌ 禁止跳过任何步骤
- ❌ 禁止未执行就输出「完成」

"""


# ============ 上下文构建 ============

def build_context(
    task_level: str,
    decision: Dict[str, Any],
    user_message: str,
    session_id: str = None
) -> str:
    """构建注入上下文
    
    根据任务等级和检测结果，构建完整的上下文内容
    """
    context_parts = []
    
    # 0. 工作流检测（最高优先级，跳过所有规则）
    workflow_name = decision.get("workflow_name")
    if workflow_name:
        logger.info(f"[soul] 工作流任务，跳过规则注入: {workflow_name}")
        return build_workflow_directive(workflow_name)
    
    # 1. 执行指令（L2/L3/L4）
    if task_level in ("L2", "L3", "L4"):
        bound_skills = get_bound_skills(task_level)
        if bound_skills:
            context_parts.append(build_execution_directive(task_level, bound_skills))
    
    # 2. 加载规则文件（支持 task_levels + rule_categories）
    detected_rules = {
        "write_operation": decision.get("write_operation", False),
        "code_guidance": decision.get("code_guidance", False),
        "agent_pool": decision.get("agent_pool", False),
        "skill_usage": decision.get("skill_usage", False),
        "self_improving": decision.get("self_improving", False),
    }
    rules_content = load_rules(task_level, detected_rules)
    if rules_content:
        context_parts.append(f"\n\n{rules_content}")
    
    # 3. 写入操作警告（L3 且涉及写入）
    if task_level == "L3" and decision.get("write_operation"):
        context_parts.append("\n\n[⚠️ 写入操作检测]")
        context_parts.append("\n该任务涉及写入操作，需要先出方案等用户确认后再执行。")
    
    return "".join(context_parts)


def build_execution_directive(task_level: str, skills: List[str]) -> str:
    """构建执行指令
    
    核心目标：让 AI 知道必须调用指定技能
    """
    if task_level == "L2":
        return f"""【执行指令】

此任务是 L2 思考分析任务。

必须调用 {skills[0]} 技能。

未调用 {skills[0]} 前，禁止输出分析内容。

"""

    elif task_level == "L3":
        return f"""【执行指令】

此任务是 L3 方案生成任务。

必须按以下流程执行：

1. 检查对话历史中是否有 L2 分析结果
   - 如有多个，使用最近的 L2 分析结果
2. 如无 L2 结果，执行分析流程：
   - 调用 deep-thinking 思考
   - 收集信息（读文件、搜索）
   - 调用 deep-thinking 形成结论
   - 输出分析结果
3. 调用 openclaw-behavior-plan 生成方案
4. 输出方案，等待用户确认

未完成前置流程前，禁止输出方案内容。

"""

    elif task_level == "L4":
        return f"""【执行指令】

此任务是 L4 方案执行任务。

必须调用 {skills[0]} 和 {skills[1]} 技能。

按步骤执行，更新进度文件。

"""

    return ""

# ============ Ollama Prompt 构建 ============

def build_ollama_prompt(user_message: str) -> str:
    """构建 Ollama 分析提示词"""
    prompt_path = PLUGIN_DIR / "prompts" / "ollama_prompt.md"
    
    if not prompt_path.exists():
        return f"""分析以下用户消息，返回 JSON 格式的决策结果。

用户消息：
{user_message}

返回格式：
{{
    "optimized_prompt": "优化后的提示词",
    "task_level": "L0/L1/L2/L3/L4",
    "phase_action": "continue/reset/complete",
    "write_operation": true/false,
    "code_guidance": true/false,
    "bound_skills": ["技能列表"]
}}
"""
    
    try:
        template = prompt_path.read_text(encoding="utf-8")
        return template.replace("{{USER_MESSAGE}}", user_message)
    except Exception as e:
        logger.error(f"加载 Ollama 提示词模板失败: {e}")
        return user_message
