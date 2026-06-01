"""
Soul Context Injector - 拦截逻辑

四层拦截 + 执行认证管理

废弃说明：
- find_execution_plan() 已移除，L4 验证改为基于技能调用
- has_execution_auth() 现在支持技能追踪验证（方案3）
- 文件验证路径已移除，不再检查 execution_plan.md 存在性
"""

import json
import re
import datetime
from fnmatch import fnmatch
from typing import Optional, Dict, Any
from pathlib import Path

from .constants import (
    logger,
    DANGEROUS_PATTERNS,
    WRITE_PATTERNS,
    WRITE_TOOLS,
    PLANNING_FILES,
    CONFIRM_KEYWORDS,
    VIOLATIONS_LOG,
)
from .state import (
    get_active_skill,
    set_active_skill,
    is_skill_in_whitelist,
)


# ============ 违规日志 ============

def log_violation(violation_type: str, tool_name: str, args: dict, task_id: str):
    """记录违规操作到日志文件（增强版）"""
    try:
        VIOLATIONS_LOG.parent.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.datetime.now().isoformat()
        
        # 构建详细违规记录
        entry_data = {
            "timestamp": timestamp,
            "task_id": task_id,
            "violation_type": violation_type,
            "tool_name": tool_name,
            "args_summary": str(args)[:500],
        }
        
        # 如果是工作流违规，添加追踪 ID
        if violation_type in ("incomplete_workflow", "skipped_step"):
            tracking_dir = Path.home() / ".hermes" / "workflow-tracking"
            if tracking_dir.exists():
                # 找最新的追踪文件
                tracking_files = list(tracking_dir.glob("*.json"))
                if tracking_files:
                    latest = max(tracking_files, key=lambda f: f.stat().st_mtime)
                    try:
                        tracking_data = json.loads(latest.read_text())
                        entry_data["tracking_id"] = tracking_data.get("tracking_id")
                        entry_data["workflow_name"] = tracking_data.get("workflow_name")
                    except Exception:
                        pass
        
        # 写入 JSON 格式日志
        with open(VIOLATIONS_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry_data, ensure_ascii=False) + "\n")
        
        logger.warning(f"[SOUL] 违规操作已记录: [{violation_type}] {tool_name}")
    except Exception as e:
        logger.error(f"[SOUL] 记录违规失败: {e}")


# ============ 文件检查 ============

def is_planning_file(path: str) -> bool:
    """检查是否为规划性文件"""
    import os
    filename = os.path.basename(path).lower()  # 提取文件名再匹配
    for pattern in PLANNING_FILES:
        if fnmatch(filename, pattern.lower()):
            return True
    return False


# ============ 危险命令检测 ============

def is_dangerous_command(command: str) -> bool:
    """检查是否为破坏性命令（永久禁止）- v5.0 精准防御
    
    设计理念：从"黑名单思维"转向"白名单+精准黑名单"
    - 默认放行所有命令
    - 只拦截真正的危险命令（系统破坏、远程代码执行攻击）
    - 使用白名单处理特殊语法（heredoc、python -c）
    """
    command_lower = command.lower().strip()
    
    # 空命令不危险
    if not command_lower:
        return False
    
    # ========== 白名单检测 ==========
    
    # 1. heredoc 白名单 - << 是输入重定向，不是管道
    if re.search(r'<<-?\s*[\'"]?\w+[\'"]?', command_lower):
        return False
    
    # 2. python -c 白名单 - Python 代码字符串，安全
    if re.search(r'python3?\s+-c\s+["\']', command_lower):
        return False
    
    # ========== 危险命令检测 ==========
    
    # 3. 远程代码执行攻击检测（最高优先级）
    # 只拦截 curl/wget + | bash/sh 的组合攻击
    rce_pattern = r'(curl|wget)\s+.*\|\s*(bash|sh|sudo|/bin/bash|/bin/sh)'
    if re.search(rce_pattern, command_lower):
        return True
    
    # 4. 系统破坏命令检测
    # 磁盘破坏
    if re.search(r'dd\s+if=.*of=/dev/(sd|hd|nvme)', command_lower):
        return True
    if re.search(r'mkfs\.\w+\s+/dev/', command_lower):
        return True
    if re.search(r'>\s*/dev/(sd|hd|nvme)', command_lower):
        return True
    
    # 系统文件破坏
    if re.search(r'>\s*/etc/(passwd|shadow|fstab)', command_lower):
        return True
    if re.search(r'>\s*/boot/', command_lower):
        return True
    
    # 根目录破坏
    # 精确匹配 rm -rf / 或 rm -rf /*，避免误拦截 /tmp/...
    if re.search(r'rm\s+(-[rf]+\s+)+/\s*$', command_lower):  # rm -rf /
        return True
    if re.search(r'rm\s+(-[rf]+\s+)+/\*', command_lower):  # rm -rf /*
        return True
    if re.search(r'chmod\s+777\s+/\s*$', command_lower):  # chmod 777 /
        return True
    if re.search(r'chown\s+-[rR].*\s+/', command_lower):
        return True
    
    # Fork 炸弹
    if re.search(r':\(\)\s*\{.*:\|:&.*\};:', command_lower):
        return True
    
    # 防火墙破坏
    if re.search(r'iptables\s+-[fFxX]', command_lower):
        return True
    if re.search(r'ufw\s+disable', command_lower):
        return True
    
    # 5. 其他命令 - 放行
    return False


# ============ 写入操作检测 ============

def is_write_operation(tool_name: str, command: str, args: dict = None) -> bool:
    """检查是否为增删改操作（需要执行认证）- 支持规划文件白名单"""
    args = args or {}
    
    # write_file 和 patch - 检查是否为规划文件
    if tool_name in WRITE_TOOLS:
        path = args.get("path", "")
        if is_planning_file(path):
            logger.info(f"[SOUL] 规划文件写入豁免: {path}")
            return False
        return True
    
    # terminal 增删改命令 - 使用更精确的匹配
    if tool_name == "terminal":
        command_lower = command.lower().strip()
        
        # 使用单词边界匹配，避免误报
        for pattern in WRITE_PATTERNS:
            pattern_clean = pattern.strip()
            # 匹配命令开头或分号/&&/||后的命令
            regex = rf'(^|[;&|]\s*){re.escape(pattern_clean)}(\s|$)'
            if re.search(regex, command_lower):
                return True
    
    return False


# ============ 执行认证管理 ============

def get_auth_file(session_id: str) -> Path:
    """获取会话专属的认证文件路径

    多会话支持：每个会话有独立的认证文件，避免互相覆盖
    """
    auth_dir = Path.home() / ".hermes" / "execution-auth"
    return auth_dir / f"{session_id}.json"


def has_execution_auth(session_id: str, expected_task: str = None) -> bool:
    """检查是否有有效的执行认证

    Args:
        session_id: 会话 ID
        expected_task: 期望的任务描述（用于校验方案内容匹配）

    Returns:
        True: 有有效认证
        False: 无认证或认证无效

    验证路径（按优先级）：
    1. Hermes approval 系统
    2. 本地认证文件（向后兼容）
    3. 技能调用追踪（新增）
    """
    # 方案1: 使用 Hermes approval 系统（推荐）
    try:
        from tools.approval import get_current_session_key, is_approved
        session_key = get_current_session_key()
        if is_approved(session_key, "soul_execution_write"):
            logger.debug(f"[SOUL] 执行认证有效 (Hermes approval): {session_key}")
            return True
    except Exception as e:
        logger.debug(f"[SOUL] Hermes approval 检查失败，降级到本地: {e}")

    # 方案2: 降级到本地文件检查（多会话支持）
    auth_file = get_auth_file(session_id)
    if auth_file.exists():
        try:
            data = json.loads(auth_file.read_text())

            # 检查会话（文件名已包含 session_id，双重验证）
            if data.get("session_id") != session_id:
                return False

            # 检查过期
            expires = datetime.datetime.fromisoformat(data["expires_at"])
            if datetime.datetime.now() > expires:
                logger.info(f"[SOUL] 执行认证已过期: {session_id}")
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


def grant_execution_auth(session_id: str, plan_path: Path = None, task_description: str = None):
    """授予执行认证

    Args:
        session_id: 会话 ID
        plan_path: 方案文件路径
        task_description: 任务描述（用于后续校验）

    同时更新 Hermes approval 系统和本地文件
    """
    success = False

    # 方案1: 使用 Hermes approval 系统
    try:
        from tools.approval import get_current_session_key, approve_session
        session_key = get_current_session_key()
        approve_session(session_key, "soul_execution_write")
        logger.info(f"[SOUL] 执行认证已授予 (Hermes approval): {session_id}")
        success = True
    except Exception as e:
        logger.warning(f"[SOUL] Hermes approval 授予失败: {e}")

    # 方案2: 本地文件（多会话支持）
    try:
        auth_file = get_auth_file(session_id)
        auth_file.parent.mkdir(parents=True, exist_ok=True)

        now = datetime.datetime.now()
        expires = now + datetime.timedelta(hours=1)

        data = {
            "session_id": session_id,
            "created_at": now.isoformat(),
            "expires_at": expires.isoformat(),
            "execution_plan": str(plan_path) if plan_path else "",
            "task_description": task_description or ""
        }

        auth_file.write_text(json.dumps(data, ensure_ascii=False, indent=2))
        logger.info(f"[SOUL] 执行认证已授予 (本地文件): session={session_id}, expires={expires}")
        success = True
    except Exception as e:
        logger.error(f"[SOUL] 授予执行认证失败 (本地文件): {e}")

    return success


# ============ 工作流完整性检查 ============

def check_workflow_completion(session_id: str, tool_name: str) -> Optional[str]:
    """检查工作流是否完整执行
    
    Args:
        session_id: 会话 ID
        tool_name: 工具名称
        
    Returns:
        None: 放行
        str: 错误消息，需要 AI 回答
    """
    # 查找当前活跃的追踪文件
    tracking_dir = Path.home() / ".hermes" / "workflow-tracking"
    if not tracking_dir.exists():
        return None
    
    # 找到最新的 in_progress 追踪文件
    active_trackings = []
    for f in tracking_dir.glob("*.json"):
        try:
            data = json.loads(f.read_text())
            if data.get("status") == "in_progress":
                # 检查是否过期（超过 2 小时）
                created_at = datetime.datetime.fromisoformat(data.get("created_at", ""))
                if datetime.datetime.now() - created_at < datetime.timedelta(hours=2):
                    active_trackings.append((f, data))
        except Exception:
            continue
    
    if not active_trackings:
        return None
    
    # 按时间排序，取最新的
    active_trackings.sort(key=lambda x: x[1]["created_at"], reverse=True)
    tracking_file, tracking_data = active_trackings[0]
    
    # 检查完成率
    total = tracking_data.get("total_steps", 0)
    completed = len(tracking_data.get("completed_steps", []))
    
    if completed < total:
        # 检测到未完成
        missing = total - completed
        workflow_name = tracking_data.get("workflow_name", "未知")
        tracking_id = tracking_data.get("tracking_id", "")
        
        logger.warning(f"[SOUL] 工作流未完成: {workflow_name} ({completed}/{total})")
        
        return f"""【🚨 工作流执行不完整】

检测到工作流「{workflow_name}」未完成：
- 总步骤：{total}
- 已完成：{completed}
- 缺失：{missing}

追踪 ID：{tracking_id}

**禁止输出「执行完成」！**

必须继续执行剩余步骤，或报告失败原因。

---

【📋 下一步操作】

1. 检查 pending_instructions 中未执行的步骤
2. 继续调用 delegate_task 执行剩余步骤
3. 所有步骤完成后才能输出「执行完成」

"""
    
    # 完成所有步骤，更新状态
    tracking_data["status"] = "completed"
    tracking_file.write_text(json.dumps(tracking_data, ensure_ascii=False, indent=2))
    logger.info(f"[SOUL] 工作流已完成: {tracking_data.get('workflow_name')}")
    
    return None


# ============ 错误信息构建 ============

def build_error_message(error_type: str, tool_name: str, args: dict) -> str:
    """构建错误信息 - 包含流程指令"""
    if error_type == "dangerous":
        command = args.get("command", "unknown")
        return f"""【🔴 永久禁止】检测到破坏性命令

命令: {command[:100]}
危险等级: 最高

此命令被永久禁止，即使有执行认证也无法执行。

---

【📋 下一步操作】

请重新设计方案，避免使用破坏性命令。
如需类似功能，考虑：
- 使用安全的替代命令
- 分步骤执行，避免一次性破坏性操作"""

    elif error_type == "no_auth":
        path = args.get("path", args.get("command", "unknown"))[:100]
        return f"""【🔴 执行认证拦截】

操作: {tool_name}
目标: {path}

此操作需要执行认证才能执行。

---

【📌 请选择处理方式】

使用 clarify 工具询问用户以下问题：

"检测到需要执行认证的写入操作，请选择处理方式："

选项:
- **确认执行**: 直接执行此操作，跳过方案流程
- **出方案**: 进入 L3 流程，先生成方案再执行
- **取消**: 放弃本次操作

---

【⏭️ 用户确认后的执行路径】

**如果选择"确认执行"**:
1. 告诉用户: "请在终端输入 /approve 或回复 '确认执行'"
2. 用户确认后，调用 grant_execution_auth(session_id, plan_path) 授予临时认证
3. 然后可以重新执行此操作

**如果选择"出方案"**:
1. 进入 L3 流程
2. 使用 deep-thinking 分析需求
3. 使用 openclaw-behavior-plan 生成执行方案 (execution_plan.md)
4. 等待用户确认方案
5. 确认后执行方案中的步骤

**如果选择"取消"**:
1. 报告用户已取消
2. 结束当前任务

---

【⚠️ 约束】

- 禁止在未获得用户确认前重新调用 {tool_name}
- 必须先使用 clarify 询问用户
- 必须按照用户选择的路径执行"""

    return f"【SOUL 拦截】未知错误: {error_type}"
