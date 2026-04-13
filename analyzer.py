"""
Soul Context Injector - 任务分析

Ollama 分析 + 本地规则降级
"""

import json
import time
import requests
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
from .workflow_cache import is_workflow_task


# ============ 本地规则客户端 ============
class LocalRuleClient:
    """本地规则客户端 - Ollama 不可用时的降级方案"""
    
    TASK_KEYWORDS = {
        "L0": ["几点", "时间", "日期", "星期", "今天", "明天", "昨天", "现在"],
        "L1": ["查看", "读取", "显示", "列出", "搜索", "查找", "获取", "看看"],
        "L2": ["分析", "比较", "评估", "设计", "优化", "思考", "为什么", "怎么"],
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
            "optimized_prompt": self._optimize_prompt(user_message),
            "task_level": task_level,
            "write_operation": self._detect_write(user_message),
            "code_guidance": self._detect_code(user_message),
            "agent_pool": self._detect_agent_pool(user_message),
            "skill_usage": self._detect_skill_usage(user_message),
            "self_improving": self._detect_self_improving(user_message),
        }
    
    def _optimize_prompt(self, prompt: str) -> str:
        replacements = [
            ("帮我看一下", "查看"),
            ("帮我分析一下", "分析"),
            ("麻烦你", ""),
            ("请问", ""),
            ("能不能", "可以"),
        ]
        for old, new in replacements:
            prompt = prompt.replace(old, new)
        return prompt.strip()
    
    def _classify_task(self, prompt: str) -> str:
        """任务分类：L0-L4"""
        lower = prompt.lower()
        
        # 【最高优先级】工作流检测
        if is_workflow_task(prompt):
            return "L1"  # 工作流视为简单执行任务
        
        # 1. 确认词检测 → L4（已有方案，用户确认执行）
        if any(kw in lower for kw in CONFIRM_KEYWORDS):
            plan_path = Path.cwd() / "execution_plan.md"
            if plan_path.exists():
                return "L4"
            return "L3"
        
        # 2. 执行类关键词 → L3（实际执行）
        exec_kws = ["创建", "实施", "执行", "部署", "安装", "卸载", "修改", "删除", "写入", "create", "implement", "deploy"]
        if any(kw in lower for kw in exec_kws):
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
                "stream": False
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
        return {
            "success": True,
            "optimized_prompt": d.get("optimized_prompt", ""),
            "task_level": d.get("task_level", "L1"),
            "write_operation": d.get("write_operation", False),
            "code_guidance": d.get("code_guidance", False),
            "agent_pool": d.get("agent_pool", False),
            "skill_usage": d.get("skill_usage", False),
            "self_improving": d.get("self_improving", False),
        }
    
    try:
        # 尝试提取 JSON
        json_start = response.find("{")
        json_end = response.rfind("}") + 1
        if json_start != -1 and json_end > json_start:
            json_str = response[json_start:json_end]
            d = json.loads(json_str)
            return _build_result(d)
    except Exception as e:
        logger.warning(f"[soul] 解析决策失败: {e}")
    
    # 降级：返回默认值
    return {"success": False, "error": "parse_failed"}


# ============ 分析入口 ============

def analyze_task(user_message: str) -> Dict[str, Any]:
    """分析用户任务
    
    优先级：
    1. 工作流检测
    2. Ollama 分析
    3. 本地规则降级
    """
    # 【最高优先级】工作流检测
    if is_workflow_task(user_message):
        logger.info(f"[SOUL] 检测到工作流任务，跳过 L3 分类")
        return {
            "success": True,
            "optimized_prompt": user_message,
            "task_level": "L1",
            "write_operation": False,
            "code_guidance": False,
            "agent_pool": False,
            "skill_usage": True,
            "self_improving": False,
        }
    
    # Ollama 分析
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
    
    # 降级：本地规则
    if not decision or not decision.get("success"):
        logger.info("[soul] 使用本地规则降级分析")
        decision = local_client.analyze(user_message)
    
    return decision
