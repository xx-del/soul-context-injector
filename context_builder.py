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
    
    设计原则：
    - 无流程锁定，保证灵活性和递归性
    - 各阶段可以互相跳转（L4无方案→回退L3）
    - 规则文件中无"锁定"概念
    """
    if task_level == "L4":
        return {
            "current_phase": "Phase 1",
            "phase_step": "Step 1",
            "flow_locked": False  # 不锁定，允许回退L3
        }
    elif task_level == "L3":
        return {
            "current_phase": "Phase 0",
            "phase_step": "Step 1",
            "flow_locked": True  # 强制锁定，必须按流程执行（调用 openclaw-behavior-plan）
        }
    elif task_level == "L2":
        return {
            "current_phase": "Phase 0",
            "phase_step": "Step 1",
            "flow_locked": True  # 强制 deep-thinking
        }
    return {
        "current_phase": None,
        "phase_step": None,
        "flow_locked": False
    }


# ============ 技能执行指令 ============




# ============ 工作流执行指令 ============




# ============ L2/L3/L4 强制执行指令 ============










def _clean_phase_info(phase_info) -> str:
    """清理 phase_info 内容
    
    Args:
        phase_info: 原始 phase_info（str 或 dict）
    
    Returns:
        清理后的纯文本描述
    """
    import re
    from .constants import SENSITIVE_PATTERNS, PHASE_INFO_MAX_LENGTH
    
    # 类型检查
    if isinstance(phase_info, str):
        raw_text = phase_info
    elif isinstance(phase_info, dict):
        # 提取关键字段
        name = phase_info.get("name", "")
        desc = phase_info.get("description", "")
        raw_text = f"{name}: {desc}" if name or desc else ""
    else:
        logger.warning(f"[SOUL-ENFORCER] phase_info 类型不支持: {type(phase_info)}")
        return ""
    
    # 移除 JSON 格式字符串
    if raw_text.startswith("{") or raw_text.startswith("["):
        return ""
    
    # 移除敏感信息
    cleaned = raw_text
    for pattern in SENSITIVE_PATTERNS:
        cleaned = re.sub(pattern, '[REDACTED]', cleaned, flags=re.IGNORECASE)
    
    # 限制长度
    if len(cleaned) > PHASE_INFO_MAX_LENGTH:
        cleaned = cleaned[:PHASE_INFO_MAX_LENGTH] + "..."
    
    # 移除多余空白
    cleaned = " ".join(cleaned.split())
    
    return cleaned.strip()


# ============ 上下文构建 ============

def build_context(
    task_level: str,
    decision: Dict[str, Any],
    user_message: str,
    session_id: str = None
) -> str:
    """构建注入上下文 - 只加载规则文件"""
    context_parts = []
    
    # 0. 技能检测
    skill_name = decision.get("skill_name")
    if skill_name:
        logger.info(f"[soul] 技能任务，加载规则: {skill_name}")
        return load_rules("S", {"skill_usage": True})
    
    # 1. 工作流检测
    workflow_name = decision.get("workflow_name")
    if workflow_name and workflow_name not in ("false", "null", "", "none"):
        logger.info(f"[soul] 工作流任务，加载规则: {workflow_name}")
        return load_rules("W", {})
    
    # 2. 加载规则文件
    detected_rules = {
        "write_operation": True,
        "code_guidance": decision.get("code_guidance", False),
        "agent_pool": decision.get("agent_pool", False),
        "skill_usage": True,
        "self_improving": decision.get("self_improving", False),
    }
    rules_content = load_rules(task_level, detected_rules)
    if rules_content:
        context_parts.append(f"\n\n{rules_content}")
    
    return "".join(context_parts)


# ============ Ollama Prompt 构建 ============

def build_ollama_prompt(user_message: str) -> str:
    """构建 Ollama 分析提示词
    
    注入内容：
    1. 工作流名称列表（用于精确匹配）
    2. pending 方案状态（用于 L4 判断）
    """
    prompt_path = PLUGIN_DIR / "prompts" / "ollama_prompt.md"
    
    # 构建 phase_context
    phase_context_parts = []

    # 1. 注入活跃工作流名称（供 Ollama 精确匹配）
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
    
    if not prompt_path.exists():
        return f"""分析以下用户消息，返回 JSON 格式的决策结果。

用户消息：
{user_message}

返回格式：
{{
    "task_level": "L0/L1/L2/L3/L4",
    "workflow_name": "匹配工作流时填名称，否则填 false",
    "write_operation": true/false,
    "code_guidance": true/false,
    "agent_pool": true/false,
    "self_improving": true/false
}}
"""
    
    try:
        template = prompt_path.read_text(encoding="utf-8")
        # 替换占位符（单花括号）
        result = template.replace("{user_message}", user_message)
        result = result.replace("{phase_context}", phase_context)
        return result
    except Exception as e:
        logger.error(f"加载 Ollama 提示词模板失败: {e}")
        return user_message
