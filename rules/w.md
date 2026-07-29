# W 工作流任务

## 【强制执行】

检测到工作流任务，需要调用 workflow-manager 技能。

1. 【第一步】调用 skill_view(name="workflow-manager") 加载技能
2. 【第二步】按照 workflow-manager SKILL.md 中的步骤顺序执行
3. 【禁止】跳过任何步骤
4. 【禁止】未调用技能直接执行
5. 【禁止】使用历史数据代替执行

## 执行前验证清单

在输出最终结果前，确认以下项全部完成：

- [ ] 已调用 skill_view(name="workflow-manager")
- [ ] 已读取工作流定义（WORKFLOW.md）
- [ ] 已分析步骤依赖关系
- [ ] 已通过 agent-pool 技能匹配 agent
- [ ] 已调用 delegate_task 执行每个步骤
- [ ] 已汇总结果并生成报告

⚠️ 验证清单未完成 → 禁止输出最终结果
