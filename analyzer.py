"""
Soul Context Injector - 任务分析

工作流本地检测 + Ollama 分析 + 本地规则降级
"""

import json
import time
import requests
import yaml
from typing import Dict, Any, Optional
from functools import lru_cache
from pathlib import Path

from .constants import (
    logger,
    OLLAMA_URL,
    DEFAULT_MODEL,
    TIMEOUT_MS,
    MAX_RETRIES,
    RULES_DIR,
    RULES_INDEX_PATH,
    CONFIRM_KEYWORDS,
    PLUGIN_DIR,
)


# ============ 工作流本地检测 ============

def detect_workflow_local(user_message: str) -> Optional[Dict[str, Any]]:
    """本地工作流检测（精确匹配，不调用 Ollama）
    
    匹配规则：
    1. 完全匹配工作流节点名称
    2. 包含"工作流"三字 + 名称关键词
    3. 包含"流程"二字 + 名称关键词
    4. 用户消息包含工作流名称/标签（模糊匹配）
    
    Returns:
        匹配成功返回 decision 字典，否则返回 None
    """
    workflows_dir = Path.home() / ".hermes" / "workflows"
    index_path = workflows_dir / "_index.yaml"
    
    if not index_path.exists():
        return None
    
    try:
        with open(index_path, 'r', encoding='utf-8') as f:
            index = yaml.safe_load(f)
        
        if not index or 'workflows' not in index:
            return None
        
        workflow_names = []
        workflow_tags = []
        for wf in index.get('workflows', []):
            if wf.get('status') == 'active':
                name = wf.get('name', '')
                if name:
                    workflow_names.append(name)
                # 收集标签
                for tag in wf.get('tags', []):
                    if tag not in workflow_tags:
                        workflow_tags.append(tag)
        
        if not workflow_names and not workflow_tags:
            return None
        
        msg_lower = user_message.lower().strip()
        
        # 1. 完全匹配工作流名称
        for name in workflow_names:
            if msg_lower == name.lower():
                logger.info(f"[soul] 工作流本地检测命中（完全匹配）: {name}")
                return {
                    "success": True,
                    "task_level": "W",
                    "workflow_name": name,
                    "write_operation": False,
                    "code_guidance": False,
                    "agent_pool": False,
                    "skill_usage": True,
                    "self_improving": False,
                }
        
        # 2. 包含"工作流"三字 → 必须包含完整工作流名称
        if "工作流" in user_message:
            matched_name = None
            for name in workflow_names:
                if name.lower() in msg_lower:
                    matched_name = name
                    break

            if matched_name:
                logger.info(f"[soul] 工作流本地检测命中（包含'工作流'+完整名称）: {matched_name}")
                return {
                    "success": True,
                    "task_level": "W",
                    "workflow_name": matched_name,
                    "write_operation": False,
                    "code_guidance": False,
                    "agent_pool": False,
                    "skill_usage": True,
                    "self_improving": False,
                }
            else:
                # 包含"工作流"但未匹配到完整名称 → 返回 W 但不指定具体工作流
                logger.info(f"[soul] 工作流本地检测命中（包含'工作流'但未匹配具体名称）")
                return {
                    "success": True,
                    "task_level": "W",
                    "workflow_name": None,
                    "write_operation": False,
                    "code_guidance": False,
                    "agent_pool": False,
                    "skill_usage": True,
                    "self_improving": False,
                }
        
        # 3. 包含"流程"二字 → 必须包含完整工作流名称
        if "流程" in user_message:
            matched_name = None
            for name in workflow_names:
                if name.lower() in msg_lower:
                    matched_name = name
                    break

            if matched_name:
                logger.info(f"[soul] 工作流本地检测命中（包含'流程'+完整名称）: {matched_name}")
                return {
                    "success": True,
                    "task_level": "W",
                    "workflow_name": matched_name,
                    "write_operation": False,
                    "code_guidance": False,
                    "agent_pool": False,
                    "skill_usage": True,
                    "self_improving": False,
                }

        # 4. 移除纯模糊匹配规则（v5.7.0 修复）
        # 原代码问题：
        #   for name in workflow_names:
        #       if name.lower() in msg_lower:  # ❌ "home" 会匹配 "home漏扫"
        # 修复：完全移除此规则，只保留以上精确匹配
        # 理由：短工作流名称会错误匹配任何包含它的用户消息

        return None
    
    except Exception as e:
        logger.warning(f"[soul] 工作流本地检测失败: {e}")
        return None


# ============ 本地规则客户端 ============
class LocalRuleClient:
    """本地规则客户端 - Ollama 不可用时的降级方案"""
    
    TASK_KEYWORDS = {
        "L0": ["几点", "时间", "日期", "星期", "今天", "明天", "昨天", "现在",
               "你好", "嗨", "hello", "hi", "早上好", "晚上好", "how are you"],
        "L1": ["查看", "读取", "显示", "列出", "搜索", "查找", "获取", "看看", "浏览", "打开"],
        "L2": [
            "分析", "比较", "评估", "设计", "优化", "思考", "为什么", "怎么",
            "制定", "规划", "方案", "研究", "探讨", "推导", "计算", "总结",
            "判断", "诊断", "解析", "理解", "归纳", "对比", "改进", "建议"
        ],
        "L3": ["创建", "修改", "删除", "部署", "重启", "安装", "卸载", "配置", "写入", "帮我做"]
    }
    
    WRITE_KEYWORDS = ["创建", "修改", "删除", "写入", "保存", "重启", "配置", "安装", "卸载", "部署", "更新"]
    CODE_KEYWORDS = ["代码", "编程", "调试", "编译", "运行", "脚本", "程序", "函数", "类"]
    AGENT_POOL_KEYWORDS = ["同时", "并行", "批量", "多个", "parallel", "batch", "同时处理"]
    SELF_IMPROVING_KEYWORDS = ["记住", "纠正", "学习", "改进", "优化流程", "更新记忆", "下次", "remember", "learn", "不再"]
    
    def analyze(self, user_message: str) -> Dict[str, Any]:
        """本地规则分析"""
        task_level = self._classify_task(user_message)
        
        return {
            "success": True,
            "task_level": task_level,
            "workflow_name": None,  # 本地降级不检测工作流，返回 None
            "write_operation": self._detect_write(user_message),
            "code_guidance": self._detect_code(user_message),
            "agent_pool": self._detect_agent_pool(user_message),
            "skill_usage": self._detect_skill_usage(user_message),
            "self_improving": self._detect_self_improving(user_message),
        }
    
    def _classify_task(self, prompt: str) -> str:
        """任务分类：L0-L4
        
        本地降级规则，与 Ollama 分析路径保持一致：
        0. 工作流检测（最高优先级）
        1. 确认词检测
        2. 执行类关键词
        3. 规划类关键词
        4. 简单查询
        5. 默认保守判断
        """
        lower = prompt.lower()
        
        # 0. 工作流检测（最高优先级，与 Ollama 路径一致）
        workflow_result = detect_workflow_local(prompt)
        if workflow_result:
            logger.info("[soul] 本地降级：工作流检测命中")
            return "W"
        
        # 1. 确认词检测（优化后）
        if any(kw in lower for kw in CONFIRM_KEYWORDS):
            
            # 步骤1.1: 排除"同意后执行"模式（这是描述执行方式，不是确认已有方案）
            confirm_then_exec_patterns = [
                "同意后执行", "同意后实施", "同意后部署",
                "确认后执行", "确认后实施", "确认后部署",
                "批准后执行", "批准后实施",
                "我同意后执行", "我确认后执行",
            ]
            has_confirm_then_exec = any(p in lower for p in confirm_then_exec_patterns)
            
            if not has_confirm_then_exec:
                # 步骤1.2: 纯确认词检测（只包含确认词+标点，无其他任务内容）
                stripped = lower.strip()
                pure_confirm = any(
                    stripped == kw or 
                    stripped.rstrip("。，！？!?.") == kw 
                    for kw in ["是", "同意", "确认", "执行", "好的", "可以", 
                              "ok", "yes", "需要", "没问题", "开始吧", "执行吧"]
                )
                
                if pure_confirm:
                    # 纯确认词 → L4（不再要求方案文件存在）
                    return "L4"
                
                # 步骤1.3: 短消息+确认词 → L4
                if len(stripped) <= 20:
                    confirm_prefix = any(stripped.startswith(kw) for kw in CONFIRM_KEYWORDS)
                    if confirm_prefix:
                        return "L4"
                
                # 步骤1.4: 检查是否包含新任务描述
                new_task_keywords = [
                    "设计", "制定", "创建", "生成", "优化方案",
                    "分析", "修复", "改进", "重构", "实现"
                ]
                has_new_task = any(kw in lower for kw in new_task_keywords)
                
                if not has_new_task:
                    # 确认词但不是新任务 → 返回 L4，由大模型从上下文判断
                    return "L4"
            
            # 继续到下面的关键词判断逻辑（不再直接return "L3"）
        
        # 2. 执行类关键词 → L3（实际执行）
        exec_kws = ["创建", "实施", "执行", "部署", "安装", "卸载", "修改", "删除", "写入", "create", "implement", "deploy"]
        if any(kw in lower for kw in exec_kws):
            return "L3"

        # 2.5. 写入操作检测 → 至少L3（规则约束：L0/L1不涉及写入）
        # L0规则: 不调用工具，不执行命令
        # L1规则: 不涉及写入操作
        if self._detect_write(lower):
            return "L3"
        
        # 3. 规划类关键词 → L2（分析规划，非执行）
        planning_kws = ["制定方案", "规划", "分析", "评估", "设计", "生成计划", "写方案", "帮我做"]
        if any(kw in lower for kw in planning_kws):
            return "L2"
        
        # 4. 简单查询 → 匹配关键词表
        for level, keywords in self.TASK_KEYWORDS.items():
            if any(kw in lower for kw in keywords):
                return level
        
        # 5. 默认保守判断 → L2（先分析，再决定是否执行）
        return "L2"
    
    def _detect_write(self, prompt: str) -> bool:
        return any(kw in prompt for kw in self.WRITE_KEYWORDS)
    
    def _detect_code(self, prompt: str) -> bool:
        return any(kw in prompt for kw in self.CODE_KEYWORDS)
    
    def _detect_agent_pool(self, prompt: str) -> bool:
        """检测是否需要并行处理多个任务"""
        return any(kw in prompt for kw in self.AGENT_POOL_KEYWORDS)
    
    def _detect_skill_usage(self, prompt: str) -> bool:
        """检测是否涉及技能使用
        
        大多数任务都可以使用技能辅助，默认返回 True
        只有明确是纯聊天时才返回 False
        """
        # 纯聊天/问候场景返回 False
        chat_keywords = ["你好", "嗨", "早上好", "晚上好", "hello", "hi", "怎么样"]
        if any(kw in prompt.lower() for kw in chat_keywords) and len(prompt) < 20:
            return False
        return True
    
    def _detect_self_improving(self, prompt: str) -> bool:
        """检测是否涉及自我改进/学习"""
        return any(kw in prompt for kw in self.SELF_IMPROVING_KEYWORDS)


# 全局实例
local_client = LocalRuleClient()


# ============ 规则加载 ============
@lru_cache(maxsize=50)
def load_rule_file(filename: str) -> str:
    """加载并缓存规则文件"""
    try:
        path = RULES_DIR / filename
        if path.exists():
            return path.read_text(encoding="utf-8")
    except Exception as e:
        logger.warning(f"加载规则文件失败 {filename}: {e}")
    return ""


def load_rules(task_level: str, detected_rules: Dict[str, bool]) -> str:
    """根据任务类型和检测规则加载对应规则文件"""
    try:
        index_content = load_rule_file("index.json")
        if not index_content:
            return ""
        
        index = json.loads(index_content)
        files = set()
        
        # 按任务类型加载
        if task_level in index.get("task_levels", {}):
            files.update(index["task_levels"][task_level].get("files", []))
        
        # 按规则类别加载
        for rule_name, is_detected in detected_rules.items():
            if is_detected and rule_name in index.get("rule_categories", {}):
                files.update(index["rule_categories"][rule_name].get("files", []))
        
        # 加载所有文件内容
        contents = []
        for f in files:
            content = load_rule_file(f)
            if content:
                contents.append(content)
        
        return "\n\n".join(contents)
    except Exception as e:
        logger.error(f"加载规则失败: {e}")
        return ""


# ============ Ollama 客户端 ============

def call_ollama(prompt: str, model: str = DEFAULT_MODEL, timeout: float = None) -> Optional[str]:
    """调用 Ollama API（同步版本）"""
    if timeout is None:
        timeout = TIMEOUT_MS / 1000
    
    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {"num_ctx": 12288}
            },
            timeout=timeout
        )
        response.raise_for_status()
        result = response.json()
        return result.get("response", "")
    except Exception as e:
        logger.warning(f"[soul] Ollama 调用失败: {e}")
        return None


def call_ollama_with_retry(prompt: str, model: str = DEFAULT_MODEL, max_retries: int = MAX_RETRIES) -> Optional[str]:
    """带重试的 Ollama 调用"""
    import time as time_module
    
    last_error = None
    for attempt in range(max_retries):
        try:
            result = call_ollama(prompt, model)
            if result:
                return result
        except Exception as e:
            last_error = e
            logger.warning(f"[soul] Ollama 调用失败 (尝试 {attempt + 1}/{max_retries}): {e}")
        
        if attempt < max_retries - 1:
            delay = 2 ** attempt
            logger.info(f"[soul] 等待 {delay}s 后重试...")
            time_module.sleep(delay)
    
    logger.error(f"[soul] Ollama 调用最终失败: {last_error}")
    return None


# ============ 决策解析 ============

def parse_decision(response: str) -> Dict[str, Any]:
    """解析 Ollama 返回的决策"""
    def _build_result(d: dict) -> Dict[str, Any]:
        # 处理 workflow_name：字符串 "false"/"null"/空字符串 → Python None
        workflow_name = d.get("workflow_name")
        if workflow_name in ("false", "null", "", "none", "None", "FALSE", "False"):
            workflow_name = None
        
        return {
            "success": True,
            "task_level": d.get("task_level", "L1"),
            "workflow_name": workflow_name,
            "write_operation": d.get("write_operation", False),
            "code_guidance": d.get("code_guidance", False),
            "agent_pool": d.get("agent_pool", False),
            "skill_usage": True,  # 常驻开启，不需要判断
            "self_improving": d.get("self_improving", False),
        }
    
    try:
        # 尝试提取 JSON
        json_start = response.find("{")
        json_end = response.rfind("}") + 1
        if json_start != -1 and json_end > json_start:
            json_str = response[json_start:json_end]
            d = json.loads(json_str)
            # 记录解析结果，包含 workflow_name
            logger.info(f"[soul] Ollama 解析结果: task_level={d.get('task_level')}, workflow_name={d.get('workflow_name')}")
            return _build_result(d)
    except Exception as e:
        logger.warning(f"[soul] 解析决策失败: {e}")
    
    # 降级：返回默认值
    return {"success": False, "error": "parse_failed"}


# ============ 分析入口 ============

def analyze_task(user_message: str) -> Dict[str, Any]:
    """分析用户任务
    
    优先级：
    1. 工作流本地检测（精确匹配，不调用 Ollama）
    2. Ollama 分析
    3. 本地规则降级
    """
    # 1. 工作流本地检测（最高优先级）
    workflow_result = detect_workflow_local(user_message)
    if workflow_result:
        return workflow_result
    
    # 2. Ollama 分析
    decision = None
    try:
        from .context_builder import build_ollama_prompt
        prompt = build_ollama_prompt(user_message)
        ollama_result = call_ollama_with_retry(prompt)
        if ollama_result:
            decision = parse_decision(ollama_result)
            if decision.get("success"):
                logger.info(f"[soul] Ollama 分析成功: task_level={decision['task_level']}")
    except Exception as e:
        logger.warning(f"[soul] Ollama 分析失败: {e}")
    
    # 3. 降级：本地规则
    if not decision or not decision.get("success"):
        logger.info("[soul] 使用本地规则降级分析")
        decision = local_client.analyze(user_message)
    
    return decision
