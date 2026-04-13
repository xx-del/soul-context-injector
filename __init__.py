"""
Soul Context Injector - Hermes Plugin v5.2

任务等级体系 + 技能绑定 + 智能分析 + 工作流检测
- L0: 微任务（直接回答）
- L1: 简单查询（直接执行）
- L2: 思考任务（deep-thinking）
- L3: 方案生成（deep-thinking + openclaw-behavior-plan）
- L4: 方案执行（planning-with-files + agent-pool）

v5.2 更新：
- 修复本地降级模式下缺失的检测字段
- 新增 agent_pool / skill_usage / self_improving 检测
- 删除未使用的导入和函数
"""

import logging
from typing import Optional, Dict, Any

# 导入各模块
from .constants import logger, CONFIRM_KEYWORDS
from .state import (
    set_active_skill,
    get_active_skill,
    is_skill_in_whitelist,
)
from .analyzer import analyze_task
from .context_builder import build_context
from .interceptor import (
    is_dangerous_command,
    is_write_operation,
    has_execution_auth,
    grant_execution_auth,
    find_execution_plan,
    log_violation,
    build_error_message,
)


# ============ Plugin Hooks ============

def pre_llm_call_hook(
    session_id: str,
    user_message: str,
    conversation_history: list,
    is_first_turn: bool,
    model: str,
    platform: str,
    **kwargs
) -> Optional[Dict[str, str]]:
    """
    pre_llm_call Hook - 在每轮对话前注入上下文
    
    流程：
    1. 用户确认检测 → 授予执行认证
    2. 任务分析（工作流检测 + Ollama + 本地降级）
    3. 上下文注入
    """
    if not user_message or not user_message.strip():
        return None
    
    logger.debug(f"[soul] 处理消息: {user_message[:100]}...")
    
    try:
        # 1. 检查用户确认词 - 授予执行认证
        if any(kw in user_message for kw in CONFIRM_KEYWORDS):
            plan_path = find_execution_plan()
            if plan_path:
                grant_execution_auth(session_id, plan_path)
        
        # 2. 分析任务
        decision = analyze_task(user_message)
        task_level = decision.get("task_level", "L1")
        
        # 3. 构建注入上下文
        context = build_context(task_level, decision, user_message, session_id)
        
        if context:
            logger.info(f"[soul] 注入上下文 {len(context)} 字符，任务等级: {task_level}")
            return {"context": context}
    
    except Exception as e:
        logger.error(f"[soul] 处理失败: {e}")
    
    return None


def pre_tool_call_hook(
    tool_name: str,
    args: dict,
    task_id: str,
    session_id: str,
    **kwargs
) -> Optional[Dict[str, str]]:
    """
    pre_tool_call Hook - 四层拦截 + 技能白名单
    
    Layer 1: 技能白名单 - 最优先放行
    Layer 2: 破坏性命令 - 永久禁止
    Layer 3: 增删改操作 - 需要执行认证
    Layer 4: 其他 - 直接放行
    """
    
    # 技能加载检测：skill_view 调用时自动设置 active_skill
    if tool_name == "skill_view" and args.get("name"):
        skill_name = args.get("name")
        set_active_skill(skill_name)
        logger.info(f"[SOUL] 技能加载: {skill_name}")
    
    # Layer 1: 技能白名单 - 最优先放行
    active_skill = get_active_skill()
    if active_skill and is_skill_in_whitelist(active_skill):
        logger.info(f"[SOUL] 技能白名单放行: skill={active_skill}, tool={tool_name}")
        return None
    
    # 提取 terminal 命令
    command = args.get("command", "") if tool_name == "terminal" else ""
    
    # Layer 2: 破坏性命令 - 永久禁止
    if tool_name == "terminal" and is_dangerous_command(command):
        log_violation("dangerous", tool_name, args, task_id)
        logger.warning(f"[SOUL] 拦截破坏性命令: {command[:50]}")
        return {"error": build_error_message("dangerous", tool_name, args)}
    
    # Layer 3: 增删改操作 - 检查执行认证
    if is_write_operation(tool_name, command, args):
        if not has_execution_auth(session_id):
            log_violation("no_auth", tool_name, args, task_id)
            logger.warning(f"[SOUL] 拦截未认证操作: {tool_name}")
            return {"error": build_error_message("no_auth", tool_name, args)}
    
    # Layer 4: 其他 - 直接放行
    return None


def post_tool_call_hook(
    tool_name: str,
    args: dict,
    result: dict,
    task_id: str,
    session_id: str,
    **kwargs
):
    """post_tool_call Hook - 清理技能上下文"""
    pass


def register(ctx):
    """插件注册入口"""
    ctx.register_hook("pre_llm_call", pre_llm_call_hook)
    ctx.register_hook("pre_tool_call", pre_tool_call_hook)
    ctx.register_hook("post_tool_call", post_tool_call_hook)
    logger.info("[soul-context-injector] 插件已加载 v5.2.1")