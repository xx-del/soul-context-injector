"""
Soul Context Injector - 工作流触发词缓存

动态加载工作流触发词，支持自动刷新
"""

import yaml
import time
from pathlib import Path
from typing import Set, Optional

from .constants import (
    logger,
    WORKFLOWS_DIR,
    WORKFLOWS_INDEX,
    WORKFLOW_MANAGER_SKILL,
)


class WorkflowTriggerCache:
    """工作流触发词缓存 - 动态加载，支持刷新
    
    数据来源：
    1. _index.yaml: 工作流名称、标签
    2. workflow-manager SKILL.md: metadata.trigger
    """
    
    _instance: Optional['WorkflowTriggerCache'] = None
    _triggers_cache: Optional[Set[str]] = None
    _last_refresh: Optional[float] = None
    _cache_ttl: int = 300  # 5分钟缓存
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def get_triggers(self) -> Set[str]:
        """获取工作流触发词集合（带缓存）"""
        now = time.time()
        
        # 缓存过期或首次加载
        if self._triggers_cache is None or \
           (self._last_refresh and now - self._last_refresh > self._cache_ttl):
            self._triggers_cache = self._load_all_triggers()
            self._last_refresh = now
            logger.info(f"[SOUL] 工作流触发词已加载: {len(self._triggers_cache)} 个")
        
        return self._triggers_cache
    
    def refresh(self) -> Set[str]:
        """强制刷新缓存"""
        self._triggers_cache = None
        self._last_refresh = None
        return self.get_triggers()
    
    def _load_all_triggers(self) -> Set[str]:
        """从多个数据源加载触发词"""
        triggers: Set[str] = set()
        
        # 1. 从 _index.yaml 加载
        triggers.update(self._load_from_index())
        
        # 2. 从 workflow-manager SKILL.md 加载
        triggers.update(self._load_from_skill())
        
        return triggers
    
    def _load_from_index(self) -> Set[str]:
        """从 _index.yaml 加载工作流名称和标签"""
        triggers: Set[str] = set()
        
        try:
            if not WORKFLOWS_INDEX.exists():
                logger.warning(f"[SOUL] 工作流索引文件不存在: {WORKFLOWS_INDEX}")
                return triggers
            
            with open(WORKFLOWS_INDEX, 'r', encoding='utf-8') as f:
                index = yaml.safe_load(f)
            
            if not index or 'workflows' not in index:
                return triggers
            
            for workflow in index.get('workflows', []):
                # 只加载 active 状态的工作流
                if workflow.get('status') != 'active':
                    continue
                
                # 添加工作流名称
                name = workflow.get('name', '')
                if name:
                    triggers.add(name.lower())
                
                # 添加标签
                for tag in workflow.get('tags', []):
                    triggers.add(tag.lower())
        
        except Exception as e:
            logger.error(f"[SOUL] 加载工作流索引失败: {e}")
        
        return triggers
    
    def _load_from_skill(self) -> Set[str]:
        """从 workflow-manager SKILL.md 加载触发词"""
        triggers: Set[str] = set()
        
        try:
            if not WORKFLOW_MANAGER_SKILL.exists():
                logger.warning(f"[SOUL] 技能文件不存在: {WORKFLOW_MANAGER_SKILL}")
                return triggers
            
            with open(WORKFLOW_MANAGER_SKILL, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 解析 YAML frontmatter
            if content.startswith('---'):
                parts = content.split('---', 2)
                if len(parts) >= 3:
                    frontmatter = yaml.safe_load(parts[1])
                    if frontmatter:
                        # 提取 metadata.openclaw.trigger
                        trigger_list = frontmatter.get('metadata', {}).get('openclaw', {}).get('trigger', [])
                        for t in trigger_list:
                            triggers.add(t.lower())
        
        except Exception as e:
            logger.error(f"[SOUL] 加载技能触发词失败: {e}")
        
        return triggers


# 全局实例
workflow_trigger_cache = WorkflowTriggerCache()


def is_workflow_task(user_message: str) -> bool:
    """检测是否为工作流任务
    
    动态匹配：从 _index.yaml 和 SKILL.md 加载触发词
    
    Args:
        user_message: 用户消息
        
    Returns:
        bool: 是否为工作流任务
    """
    lower = user_message.lower()
    triggers = workflow_trigger_cache.get_triggers()
    
    for trigger in triggers:
        if trigger in lower:
            logger.info(f"[SOUL] 匹配工作流触发词: {trigger}")
            return True
    
    return False
