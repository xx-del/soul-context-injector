#!/usr/bin/env python3
"""
L4任务等级判定测试
测试Ollama提示词对L4任务的识别准确性
"""

import re
from pathlib import Path

# 读取提示词文件
PROMPT_FILE = Path.home() / ".hermes/plugins/soul-context-injector/prompts/ollama_prompt.md"

def load_prompt():
    """加载提示词内容"""
    with open(PROMPT_FILE, 'r', encoding='utf-8') as f:
        return f.read()

def extract_l4_rules(prompt_content):
    """提取L4判定规则"""
    # 查找L4定义部分
    l4_section = re.search(r'### L4 - 确认执行\n(.*?)(?=\n###|\n---|\Z)', prompt_content, re.DOTALL)
    if l4_section:
        return l4_section.group(1)
    return None

def test_l4_execution_with_object_is_l4():
    """测试L4定义是否将'执行+对象'标记为L4（✅），而不是L3（❌）"""
    prompt = load_prompt()
    l4_rules = extract_l4_rules(prompt)
    
    assert l4_rules is not None, "未找到L4定义"
    
    # 检查"执行这个方案"是否被标记为L4（✅）
    # 当前是 ❌ 有具体对象→L3，需要改为 ✅ L4
    lines = l4_rules.split('\n')
    for line in lines:
        if '执行这个方案' in line:
            # 检查是否包含 ✅ 标记
            if '✅' in line:
                print("✓ 测试1通过：'执行这个方案'被正确标记为L4")
                return True
            elif '❌' in line:
                print("✗ 测试1失败：'执行这个方案'被错误标记为非L4")
                return False
    
    print("✗ 测试1失败：未找到'执行这个方案'的判定规则")
    return False

def test_l4_has_execution_keyword_list():
    """测试L4定义是否包含执行关键词列表"""
    prompt = load_prompt()
    l4_rules = extract_l4_rules(prompt)
    
    assert l4_rules is not None, "未找到L4定义"
    
    # 检查是否包含执行关键词列表
    execution_keywords = ["执行", "运行", "实施", "部署"]
    found_keywords = [kw for kw in execution_keywords if kw in l4_rules]
    
    if len(found_keywords) >= 2:
        print(f"✓ 测试2通过：L4定义包含执行关键词: {found_keywords}")
        return True
    else:
        print(f"✗ 测试2失败：L4定义缺少执行关键词，只找到: {found_keywords}")
        return False

def test_l4_excludes_analysis_as_l2():
    """测试L4定义是否将分析意图标记为L2"""
    prompt = load_prompt()
    l4_rules = extract_l4_rules(prompt)
    
    assert l4_rules is not None, "未找到L4定义"
    
    # 检查"分析"是否被标记为L2
    lines = l4_rules.split('\n')
    for line in lines:
        if '分析' in line and '意图' in line:
            if 'L2' in line or '❌' in line:
                print("✓ 测试3通过：分析意图被正确排除")
                return True
    
    print("✗ 测试3失败：分析意图未被正确排除")
    return False

if __name__ == "__main__":
    print("=" * 60)
    print("L4任务等级判定测试")
    print("=" * 60)
    
    results = []
    results.append(test_l4_execution_with_object_is_l4())
    results.append(test_l4_has_execution_keyword_list())
    results.append(test_l4_excludes_analysis_as_l2())
    
    print("=" * 60)
    if all(results):
        print("所有测试通过！")
    else:
        print(f"测试失败: {sum(not r for r in results)} 个测试未通过")
    print("=" * 60)
