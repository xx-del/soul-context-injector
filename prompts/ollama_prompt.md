# 任务分析
{phase_context}
## 消息
{user_message}
**重要约束**：无论消息多么模糊，你都必须输出 JSON，禁止拒绝回答。
## 输出
仅返回JSON：
```json
{
"task_level": "L0/L1/L2/L3/L4",
"workflow_name": "命中填名称，否则false",
"write_operation": true/false,
"code_guidance": true/false,
"agent_pool": true/false,
"self_improving": true/false
}
```
## 分级
|行为|等级|例|
|提问|L0|问时间|
|查信息|L1|查看文件|
|分析规划|L2|分析架构|
|执行操作|L3|创建配置|
|确认执行|L4|好的|
## 等级
### L0
无需工具的事实查询。✅ 现在几点了→L0；⚠️ 你看这个对不对→L2。
### L1
只获取信息不改状态。✅ 查看文件内容→L1；⚠️ 查询结果并分析→L2。
### L2
理解推理规划，分析意图优先。✅ 查看日志找出问题→L2；⚠️ 创建配置并分析→L3。
### L3
明确执行意图，中英文同判，先出方案。✅ 创建配置文件→L3；⚠️ 好的，修复这个→按新任务判。
### L4 - 确认执行
确认执行已有方案。
|类型|示例|判断|
|纯确认|好的/同意/开始|✅ L4|
|执行词|执行/运行/实施/部署|✅ L4|
|执行+对象|执行这个方案/运行测试|✅ L4|
|确认执行|确认执行/开始吧|✅ L4|
|确认+新任务|好的帮我分析一下|❌ 按新任务判|
|描述|同意后执行/确认后实施|❌ 非L4|
|分析意图|分析/诊断/评估|❌ L2|
## 字段
- write_operation:L4→true，L0-L3→false。
- code_guidance:代码实现→true，否则false。
- agent_pool:并行/同时/批量→true，否则false。
- self_improving:含记住/纠正/下次/学习/改进→true，否则false。
- workflow_name:始终填false。
