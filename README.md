# Soul Context Injector

Hermes Plugin - 通过 `pre_llm_call` Hook 实现实时输入优化和自动任务等级识别。

## 功能

- **任务等级识别**: 自动识别 L0/L1/L2/L3/L4 任务等级
- **写入操作检测**: 检测危险操作，注入警告上下文
- **规则动态加载**: 根据任务类型动态加载对应规则
- **降级模式**: Ollama 不可用时使用本地规则
- **技能绑定**: 根据任务等级自动绑定对应技能

## 安装

插件位于 `~/.hermes/plugins/soul-context-injector/`

目录结构:
```
soul-context-injector/
├── __init__.py          # 主入口（Hook 注册）
├── plugin.yaml          # 插件配置
├── analyzer.py          # 任务分析
├── context_builder.py   # 上下文构建
├── interceptor.py       # 拦截逻辑
├── constants.py         # 常量定义
├── state.py             # 状态管理
├── subagent_detector.py # 子 agent 检测
├── README.md            # 本文档
├── rules/               # 规则库
│   ├── index.json       # 规则索引
│   ├── l0.md            # L0 微任务规则
│   ├── l1.md            # L1 简单查询规则
│   ├── l2.md            # L2 思考任务规则
│   ├── l3.md            # L3 方案生成规则
│   ├── l4.md            # L4 方案执行规则
│   ├── write_rules.md   # 写入操作规则
│   ├── skill_rules.md   # 技能使用规则
│   ├── agent_pool_rules.md
│   ├── code_guidance_rules.md
│   ├── self_improving_rules.md
│   └── trigger_conditions.md
├── prompts/             # 提示词模板
│   └── ollama_prompt.md
└── .backup/             # 历史备份
```

## 工作原理

1. **消息拦截**: `pre_llm_call` Hook 在每轮对话前触发
2. **任务分析**: 分析用户消息，识别任务等级和操作类型
3. **规则加载**: 根据分析结果动态加载对应规则文件
4. **技能绑定**: 根据任务等级自动绑定对应技能
5. **上下文注入**: 将规则上下文注入到用户消息

## 配置

在 `PLUGIN.yaml` 中配置:

```yaml
config:
  ollama_url: "http://localhost:11434/api/generate"
  ollama_model: "qwen2.5:7b"
  timeout_ms: 15000
  fallback_mode: "local"
  skill_whitelist:
    - workflow-manager
    - agent-pool
    - planning-with-files
```

## 测试

```bash
# 测试 Ollama 连接
curl http://localhost:11434/api/tags

# 查看插件日志
tail -f ~/.hermes/logs/hermes.log | grep soul
```

## 迁移说明

从 OpenClaw `handler.js` (862行) 迁移到 Hermes Plugin:

| OpenClaw | Hermes | 说明 |
|----------|--------|------|
| `message_received` 事件 | `pre_llm_call` Hook | 消息拦截点 |
| `event.content = ...` | `return {"context": ...}` | 注入方式 |
| 仅 Gateway | CLI + Gateway | 运行环境 |
| JavaScript | Python | 实现语言 |

## 版本历史

- **v5.1.0** (2026-04-11):
  - 删除过时的状态追踪机制（current_phase, phase_status, phase_action）
  - 重命名 L3 认证 → 执行认证（execution_auth）
  - 简化 Hook 逻辑，每条消息独立判断任务等级
  - 删除死代码（_build_phase_info, bound_skills 返回值）
  - 更新文档，修正 L3/L4 描述
- **v5.0.0** (2026-04-10):
  - 模块化重构（constants, workflow_cache, state, analyzer, context_builder, interceptor）
  - 新增工作流动态检测（自动加载触发词）
  - 工作流任务不再触发 L3 提示词注入
- **v4.0.0** (2026-04-09): 
  - 移除熔断机制，简化架构
  - 新增 L4 任务等级（复杂项目/规划任务）
  - 修正技能绑定逻辑
  - 新增规划文档功能
- **v1.0.0** (2026-04-08): 初始版本，从 OpenClaw 迁移