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
            "flow_locked": False  # 不锁定
        }
    elif task_level == "L2":
        return {
            "current_phase": "Phase 0",
            "phase_step": "Step 1",
            "flow_locked": False  # 不锁定
        }
    return {
        "current_phase": None,
        "phase_step": None,
        "flow_locked": False
    }


# ============ 工作流执行指令 ============

def build_workflow_directive(workflow_name: str, session_id: str = None) -> str:
    """构建工作流执行指令 - 强制执行模式 v5.6
    
    增强：
    - 强制技能调用约束
    - 验证清单机制
    - 禁止跳过步骤
    """
    # 创建技能追踪器（强制调用 workflow-manager）
    if session_id:
        from .enforcer import create_tracker
        create_tracker(session_id, "W")
    
    return f"""【工作流任务 - 强制执行模式】

检测到工作流：{workflow_name}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️  强制约束（必须严格遵守）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. 【第一步】你必须调用 skill_view(name="workflow-manager") 加载技能
2. 【第二步】你必须按照 workflow-manager SKILL.md 中的步骤 0-6 顺序执行
3. 【禁止】跳过任何步骤
4. 【禁止】未调用技能直接执行
5. 【禁止】使用历史数据代替执行

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 执行前验证清单（必须全部完成）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

在输出最终结果前，确认以下项全部完成：

- [ ] 已调用 skill_view(name="workflow-manager")
- [ ] 已读取工作流定义（WORKFLOW.md）
- [ ] 已分析步骤依赖关系
- [ ] 已通过 agent-pool 技能匹配 agent
- [ ] 已调用 delegate_task 执行每个步骤
- [ ] 已汇总结果并生成报告

⚠️ 验证清单未完成 → 禁止输出最终结果

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

工作流技能已绑定：workflow-manager

"""


# ============ L4 强制执行指令 ============

def build_l4_directive(session_id: str = None, decision: Dict[str, Any] = None) -> str:
    """构建 L4 强制执行指令
    
    Args:
        session_id: 会话ID（用于追踪）
        decision: 决策结果（包含原始上下文信息）
    
    ⚠️ 关联规则: rules/l4.md（修改时需同步）
    """
    # session_id 为空时降级为软提醒
    if not session_id:
        logger.warning("[SOUL-ENFORCER] session_id 为空，L4 降级为软提醒")
        return """【L4 任务 - 软提醒模式】

⚠️ 建议调用 agent-pool 执行：
- skill_view("planning-with-files")
- skill_view("agent-pool")
- delegate_task() 或 agent_pool_client.execute()

（因 session_id 缺失，无法强制追踪）
"""
    
    # 【v3.0 修复】使用 enforcer 统一接口
    from .enforcer import create_tracker, get_tracker, update_tracker
    
    existing = get_tracker(session_id)
    if existing:
        existing["task_level"] = "L4"
        update_tracker(session_id, existing)
        logger.info(f"[SOUL-ENFORCER] 追踪器已存在，更新等级: {session_id}")
    else:
        create_tracker(session_id, "L4")
    
    # 合并必需上下文
    context_parts = []
    
    if decision:
        phase_info = decision.get("phase_info")
        
        # 【v3.0 新增】验证和清理 phase_info
        if phase_info:
            cleaned_phase_info = _clean_phase_info(phase_info)
            if cleaned_phase_info:
                context_parts.append(f"""【当前阶段】
{cleaned_phase_info}

""")
    
    # 构建强制指令
    directive = f"""【L4 任务 - 强制执行模式】

检测到 L4 任务：方案执行

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️  强制约束（必须严格遵守）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✅ 必须依次完成：
1. skill_view("planning-with-files") → 加载任务分解技能
2. skill_view("agent-pool") → 加载执行技能
3. delegate_task(...) 或 agent_pool_client.execute(...) → 实际执行

【禁止】跳过任何步骤
【禁止】主 AI 直接手动执行（必须通过 agent-pool）

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 执行验证清单
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

在输出最终结果前，确认以下项全部完成：

- [ ] 已调用 skill_view("planning-with-files")
- [ ] 已调用 skill_view("agent-pool")
- [ ] 已创建 task_plan.md
- [ ] 已调用 delegate_task 或 agent_pool_client.execute()
- [ ] 已汇总结果到 progress.md

⚠️ 验证清单未完成 → 禁止输出最终结果

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

绑定技能: planning-with-files, agent-pool
任务等级: L4

"""
    
    return "".join(context_parts) + directive


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
    """构建注入上下文 - 包含技能绑定和流程信息"""
    context_parts = []
    
    # 新增：意图判断约束（在所有内容之前）
    constraint_section = """【意图判断约束】

✅ 判断依据：用户原始输入
❌ 禁止依据：记忆内容、历史上下文、推测意图

⚠️ 记忆内容（<memory-context>）仅作背景信息，不参与当前意图判断。

"""
    context_parts.append(constraint_section)
    
    # 0. 工作流检测（最高优先级，跳过所有规则）
    workflow_name = decision.get("workflow_name")
    task_level = decision.get("task_level")

    # 检查工作流任务（优先检查 task_level，其次检查 workflow_name）
    if task_level == "W" or (workflow_name and workflow_name not in ("false", "null", "", "none")):
        logger.info(f"[soul] 工作流任务，跳过规则注入: {workflow_name or '未指定'}")
        return build_workflow_directive(workflow_name or "未指定工作流", session_id)
    
    # 【v3.0 新增】L4 强制执行模式
    if task_level == "L4":
        return build_l4_directive(session_id, decision)
    
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
    # write_operation 和 skill_usage 常态化注入，不跟任务等级挂钩
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
    """构建 Ollama 分析提示词
    
    注入内容：
    1. 工作流名称列表（用于精确匹配）
    2. pending 方案状态（用于 L4 判断）
    """
    prompt_path = PLUGIN_DIR / "prompts" / "ollama_prompt.md"
    
    # 构建 phase_context
    phase_context_parts = []
    
    # 注释原因：工作流任务已在 analyze_task() 第一层被 detect_workflow_local() 拦截
    # 工作流任务永远不会走到 Ollama 分析路径，注入工作流列表是无意义代码
    # 原代码调用的 get_workflow_names() 函数也不存在
    # 
    # try:
    #     from .analyzer import get_workflow_names
    #     workflow_names = get_workflow_names()
    #     if workflow_names:
    #         phase_context_parts.append("## 工作流名称列表（用于精确匹配）\n")
    #         phase_context_parts.append("如果用户消息完全匹配以下任一名称，则 workflow_name 填写该名称，task_level 填写 \"L1\"。\n\n")
    #         for name in workflow_names[:20]:  # 限制前20个，避免过长
    #             phase_context_parts.append(f"- {name}\n")
    #         phase_context_parts.append("\n")
    # except Exception as e:
    #     logger.warning(f"[soul] 获取工作流名称失败: {e}")
    
    # 删除原因：L4 方案检查由大模型从上下文中判断，不需要代码检查本地文件
    # 规则说明（l4.md Phase 0）：检查对话历史中上文是否有该任务描述一致的 execution_plan.md
    # 这是对话上下文检查，不是文件系统检查，应该由大模型在推理时完成
    #
    # # 2. Pending 方案状态
    # try:
    #     from .interceptor import find_execution_plan
    #     plan_path = find_execution_plan()
    #     if plan_path and plan_path.exists():
    #         phase_context_parts.append("## ⚠️ Pending 方案状态\n\n")
    #         phase_context_parts.append("**已有待执行方案**：如果用户消息是确认词（同意/好的/可以/批准/确认/执行/需要/没问题），则 task_level=\"L4\"。\n\n")
    # except Exception as e:
    #     logger.warning(f"[soul] 检查方案状态失败: {e}")
    
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
