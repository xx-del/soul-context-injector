# SOUL 规则库 - 自我改进

版本 v1.1
更新时间 2026-04-09

## 执行前
- 加载 `~/.hermes/skills/openclaw-imports/self-improving/memory.md`
- 读取相关 domain/project 文件
- 最多读取 3 个匹配的 domain 文件

## 执行后
- 纠正 → 立即写入 corrections.md
- 失败 → 记录教训
- 可复用经验 → 写入对应文件

## 原则
- 优先使用已学规则，保持可修正
- 不因任务熟悉跳过检索
- 事实性历史 → memory/YYYY-MM-DD.md
- 可复用性能经验 → self-improving 目录

## 禁止行为
- 因任务看似熟悉就跳过检索
- 忽略已学习的规则
- 不记录纠正和失败经验
