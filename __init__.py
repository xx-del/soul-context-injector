"""
Soul Context Injector - Hermes Plugin v5.7

任务等级体系 + 工作流精确匹配 + 技能绑定 + 智能分析 + 子 agent 放行 + 工作流强制执行
- L0: 微任务（直接回答）
- L1: 简单查询 / 工作流执行（直接执行）
- L2: 思考任务（deep-thinking）
- L3: 方案生成（deep-thinking + openclaw-behavior-plan）
- L4: 方案执行（planning-with-files + agent-pool）
- W: 工作流任务（workflow-manager 强制执行）

v5.7 更新：
- 修复工作流检测模糊匹配问题
- 移除纯模糊匹配规则 (Rule 4)
- Rule 2/3 要求完整工作流名称
- 修复: 'home' 错误匹配 'home漏扫'

v5.6 更新：
- 工作流强制执行模式：增强 build_workflow_directive() 注入强制约束
- 验证清单机制：输出前必须完成技能调用验证
- enforcer 支持 W 等级：技能追踪 + 输出拦截
- 禁止行为明确化：跳过步骤、未调用技能、使用历史数据
"""

import logging
import re
from typing import Optional, Dict, Any

# 导入各模块
from .constants import logger
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
    get_auth_file,
    log_violation,
    build_error_message,
    check_workflow_completion,
)
from .subagent_detector import is_subagent


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
    0. 子 agent 放行 - 跳过上下文注入
    1. 任务分析（工作流本地检测 → Ollama → 本地降级）
    2. L4 处理：授予执行认证
    3. 上下文注入
    """
    # Periodic cleanup (1% probability to avoid overhead)
    import random
    if random.random() < 0.01:
        from .enforcer import cleanup_expired_trackers
        cleanup_expired_trackers()

    if not user_message or not user_message.strip():
        return None
    
    # Layer 0: 子 agent 放行 - 跳过上下文注入
    if is_subagent(session_id):
        logger.info(f"[SOUL] 子 agent 放行（LLM）: session={session_id}")
        return None
    
    logger.debug(f"[soul] 处理消息: {user_message[:100]}...")
    
    try:
        # 1. 分析任务（统一入口：工作流本地检测 → Ollama → 本地降级）
        decision = analyze_task(user_message)
        task_level = decision.get("task_level", "L1")
        workflow_name = decision.get("workflow_name")
        
        # 2. L4 处理：大模型自主判断是否执行方案
        # 方案路径由大模型从上下文中判断，不再通过代码查找
        if task_level == "L4" and not workflow_name:
            logger.info(f"[SOUL] L4 任务，等待大模型判断方案")
        
        # 3. 构建注入上下文
        context = build_context(task_level, decision, user_message, session_id)
        
        # 4. 创建技能追踪（L2/L3/L4 任务）
        # L0/L1 不创建追踪器，符合规则约束：
        # - L0: 不调用工具，不执行命令
        # - L1: 不涉及写入操作
        if task_level in ["L2", "L3", "L4"]:
            from .enforcer import create_tracker
            create_tracker(session_id, task_level)
        
        if context:
            log_msg = f"[soul] 注入上下文 {len(context)} 字符，任务等级: {task_level}"
            if workflow_name:
                log_msg += f"，工作流: {workflow_name}"
            logger.info(log_msg)
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
    pre_tool_call Hook - 七层拦截 + 技能白名单 + 子 agent 放行
    
    Layer 0: 强制执行检查 - 技能调用追踪（新增）
    Layer 1: 子 agent 放行 - 继承父 agent 权限
    Layer 2: 技能白名单 - 最优先放行
    Layer 3: 破坏性命令 - 永久禁止
    Layer 4: 增删改操作 - 需要执行认证
    Layer 5: 工作流完整性 - 检查是否完成所有步骤
    Layer 6: 其他 - 直接放行
    """
    
    # Layer 0: 强制执行检查（新增）
    from .enforcer import should_enforce, check_required_skills, track_skill_call, get_tracker
    
    enforce = should_enforce(session_id)
    logger.info(f"[SOUL] should_enforce({session_id}) = {enforce}, tool={tool_name}")
    
    if enforce:
        # 追踪技能调用
        if tool_name == "skill_view":
            skill_name = args.get("name")
            if skill_name:
                logger.info(f"[SOUL] 准备追踪技能调用: {skill_name}")
                result = track_skill_call(session_id, skill_name)
                logger.info(f"[SOUL] 追踪结果: {result}")
        
        # 【v3.0 新增】追踪实际执行（多路径）
        from .constants import EXECUTION_TYPES, TERMINAL_DETECTION_PATTERNS
        from .enforcer import track_execution
        
        # 1. delegate_task 工具调用
        if tool_name == "delegate_task":
            track_execution(session_id, EXECUTION_TYPES["DELEGATE_TASK"], tool_name)
        
        # 2. 终端命令检测
        if tool_name == "terminal":
            command = args.get("command", "")
            for pattern in TERMINAL_DETECTION_PATTERNS:
                if re.search(pattern, command):
                    track_execution(session_id, EXECUTION_TYPES["TERMINAL_EXECUTION"], tool_name)
                    break
        
        # 3. Python API 检测
        if tool_name == "execute_code":
            code = args.get("code", "")
            if "agent_pool_client" in code or "Orchestrator" in code:
                track_execution(session_id, EXECUTION_TYPES["PYTHON_API"], tool_name)

        # 【v3.0 新增】技能验证后自动授予认证
        tracker = get_tracker(session_id)
        if tracker:
            task_level = tracker.get("task_level")
            if task_level == "L4":
                from .interceptor import grant_execution_auth
                from .constants import REQUIRED_SKILLS_L4

                called = tracker.get("called_skills", [])
                executed_by = tracker.get("executed_by", [])

                # 技能调用完成 + 实际执行发生 → 授予认证
                if all(s in called for s in REQUIRED_SKILLS_L4) and executed_by:
                    grant_execution_auth(session_id, task_description="L4 execution verified")
                    logger.info(f"[SOUL] L4 执行认证授予: skills={called}, execution={executed_by}")

        # 输出拦截（所有输出类工具）
        from .constants import OUTPUT_TOOLS

        if tool_name in OUTPUT_TOOLS:
            all_called, error = check_required_skills(session_id)
            if not all_called:
                log_violation("missing_required_skill", tool_name, args, task_id)
                return {"action": "block", "message": error}
    
    # Layer 1: 子 agent 放行 - 继承父 agent 权限
    if is_subagent(session_id):
        logger.info(f"[SOUL] 子 agent 放行: session={session_id}, tool={tool_name}")
        return None
    
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
        return {"action": "block", "message": build_error_message("dangerous", tool_name, args)}
    
    # Layer 3: 增删改操作 - 检查执行认证
    if is_write_operation(tool_name, command, args):
        if not has_execution_auth(session_id):
            log_violation("no_auth", tool_name, args, task_id)
            logger.warning(f"[SOUL] 拦截未认证操作: {tool_name}")
            return {"action": "block", "message": build_error_message("no_auth", tool_name, args)}
    
    # Layer 4: 工作流完整性检查 - 拦截未完成的输出
    if tool_name == "send_message":
        error = check_workflow_completion(session_id, tool_name)
        if error:
            log_violation("incomplete_workflow", tool_name, args, task_id)
            logger.warning(f"[SOUL] 拦截不完整工作流输出")
            return {"action": "block", "message": error}
    
    # Layer 5: 其他 - 直接放行
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
    logger.info("[soul-context-injector] 插件已加载 v5.7")
