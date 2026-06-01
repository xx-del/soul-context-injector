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
    SKILL_BINDINGS,
)
from .analyzer import load_rules


# ============ 技能绑定函数 ============

def get_bound_skills(task_level: str) -> List[str]:
    """获取任务等级对应的绑定技能"""
    return SKILL_BINDINGS.get(task_level, [])


# ============ 流程信息构建 ============

def build_phase_info(task_level: str) -> dict:
    """根据任务等级构建流程信息
    
    L4: Phase 1 执行阶段，流程锁定
    L3: Phase 0 思考阶段，流程锁定
    L2: Phase 0 思考阶段，流程锁定（强制调用技能）
    L0/L1: 无流程
    """
    if task_level == "L4":
        return {
            "current_phase": "Phase 1",
            "phase_step": "Step 1",
            "flow_locked": True
        }
    elif task_level == "L3":
        return {
            "current_phase": "Phase 0",
            "phase_step": "Step 1",
            "flow_locked": True
        }
    elif task_level == "L2":
        return {
            "current_phase": "Phase 0",
            "phase_step": "Step 1",
            "flow_locked": True  # L2 也锁定，强制调用技能
        }
    return {
        "current_phase": None,
        "phase_step": None,
        "flow_locked": False
    }


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
    """构建注入上下文 - 包含技能绑定和流程信息"""
    context_parts = []
    
    # 0. 工作流检测（最高优先级，跳过所有规则）
    workflow_name = decision.get("workflow_name")
    # 明确判断：workflow_name 必须是非空字符串且不等于 "false"
    if workflow_name and workflow_name not in ("false", "null", "", "none"):
        logger.info(f"[soul] 工作流任务，跳过规则注入: {workflow_name}")
        return build_workflow_directive(workflow_name)
    
    # 获取绑定技能和流程信息
    bound_skills = get_bound_skills(task_level)
    phase_info = build_phase_info(task_level)
    
    # 1. 技能绑定（只显示技能名，流程说明由 lx.md 提供）
    if bound_skills:
        skill_section = f"""【📌 技能绑定】

绑定技能: {', '.join(bound_skills)}
任务等级: {task_level}

"""
        context_parts.append(skill_section)
    
    # 2. 流程锁定（核心：强制约束）
    if phase_info.get("flow_locked"):
        locked_section = f"""【🔒 流程锁定】

当前阶段: {phase_info.get('current_phase', 'unknown')}
当前步骤: {phase_info.get('phase_step', '-')}
流程状态: 锁定中（必须按流程执行）

⚠️ 流程锁定规则：
- 必须按步骤执行，不可跳过
- 必须调用绑定技能
- 直到流程完成

"""
        context_parts.append(locked_section)
    
    # 3. 加载规则文件（来自 rules/ 目录）
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
    
    # 4. 写入操作警告（L3 且涉及写入）
    if task_level == "L3" and decision.get("write_operation"):
        context_parts.append("\n\n[⚠️ 写入操作检测]")
        context_parts.append("\n该任务涉及写入操作，需要先出方案等用户确认后再执行。")
    
    # 5. 调试摘要（核心：状态可见）
    flow_locked_str = ""
    if phase_info.get("flow_locked"):
        flow_locked_str = f"\n🔒 流程锁定: {phase_info.get('current_phase', 'unknown')} - {phase_info.get('phase_step', '-')}"
    
    summary = f"""
【🔍 消息处理追踪】
📊 任务等级: {task_level}
⚠️  写入操作: {'检测到' if decision.get('write_operation') else '未检测'}
💻 代码指导: {'需要' if decision.get('code_guidance') else '不需要'}
🤖 Agent池: {'建议' if decision.get('agent_pool') else '不激活'}
🛠️  技能使用: {'重要' if decision.get('skill_usage') else '常规'}
🔄 自我改进: {'启用' if decision.get('self_improving') else '禁用'}

📎 绑定技能: {', '.join(bound_skills) if bound_skills else '无'}{flow_locked_str}
"""
    context_parts.append(summary)
    
    return "".join(context_parts)


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
