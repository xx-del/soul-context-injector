# Soul Context Injector - 使用指南

## 快速开始

插件已自动加载，无需手动操作。每次对话时会自动注入上下文。

## 功能说明

### 1. 任务等级识别

自动识别用户消息的任务等级：

|| 等级 | 触发词示例 | 行为 | 技能绑定 ||
||------|-----------|------|---------|
|| L0 | 几点、时间、今天 | 直接回答 | 无 ||
|| L1 | 查看、读取、搜索 | 直接执行 | 无 ||
|| L2 | 分析、思考、为什么 | 触发 deep-thinking | deep-thinking ||
|| L3 | 创建、修改、部署 | 生成执行方案 | deep-thinking, openclaw-behavior-plan ||
|| L4 | 确认、同意、执行 | 执行已确认方案 | planning-with-files, agent-pool ||

### 2. 写入操作保护

检测到写入操作时，自动注入警告：

```
【⚠️ 写入操作警告】

此任务涉及写入操作（修改文件、删除、网关操作等）。
**必须先出方案，等用户同意后再执行。**
```

### 3. 两层拦截机制 (v3.1)

通过 `pre_tool_call` Hook 实现两层拦截：

#### Layer 1: 破坏性命令（永久禁止）

| 类别 | 命令 | 说明 |
|------|------|------|
| 磁盘破坏 | `dd if=`, `dd of=`, `mkfs`, `format` | 格式化、覆写磁盘 |
| 系统破坏 | `> /etc/passwd`, `> /etc/shadow`, `> /boot/` | 破坏系统文件 |
| Fork 炸弹 | `:(){:|:&};:` | 进程爆炸 |
| 防火墙破坏 | `iptables -F`, `ufw disable` | 关闭防火墙 |
| 远程执行 | `\| bash`, `\| sh`, `\| sudo` | 未审查代码执行 |

**即使有 L3 认证也无法执行。**

#### Layer 2: 增删改操作（需要 L3 认证）

| 类别 | 命令/工具 |
|------|----------|
| 文件操作 | `rm`, `mv`, `cp`, `mkdir`, `touch`, `chmod`, `chown` |
| 打包解压 | `tar`, `unzip`, `gzip`, `7z` |
| 下载写入 | `curl -o`, `wget -O`, `scp`, `rsync` |
| Git 操作 | `git push`, `git commit`, `git add`, `git rm` |
| 包管理 | `pip install/uninstall`, `npm install/uninstall`, `apt install/remove` |
| 系统服务 | `systemctl start/stop/restart`, `docker run/rm/stop` |
| 工具 | `write_file`, `patch` |

#### 其他：直接放行（不处理）

所有查询类命令（`ls`, `cat`, `grep`, `git status` 等）直接放行，不进行任何处理。

### 4. 执行认证机制

**认证流程：**

```
1. 用户请求 → LLM 生成方案（L3）
2. 生成 execution_plan.md
3. 用户确认（说"同意"/"确认"/"执行"）→ 进入 L4
4. 授予执行认证（1小时有效）
5. LLM 执行操作
```

**认证条件：**
- 存在 `execution_plan.md` 文件
- 用户说了确认词
- 会话匹配
- 未过期（1小时）

**认证文件：** `~/.hermes/.soul_execution_auth`

### 5. 违规记录

被拦截的操作记录到：
```
~/.hermes/logs/soul-violations.log
```

格式：
```
[时间戳] [会话ID] 工具名: 原因 | args=参数
```

## 配置选项

编辑 `PLUGIN.yaml`：

```yaml
config:
  ollama_url: "http://localhost:11434/api/generate"
  ollama_model: "qwen2.5:7b"  # 可选其他模型
  timeout_ms: 15000
  fallback_mode: "local"  # local 或 skip
```

## 验证插件运行

### 方法1：查看日志

```bash
# CLI 模式
hermes chat
# 输入任意消息，观察是否有 [soul] 日志

# Gateway 模式
tail -f ~/.hermes/logs/hermes.log | grep soul
```

### 方法2：测试特定消息

```bash
# 测试写入检测
hermes chat
> 删除 test.txt 文件
# 应该看到写入操作警告

# 测试任务等级
> 现在几点了
# L0 - 直接回答

> 分析这个代码
# L2 - 触发思考
```

## 故障排除

### 问题：插件未加载

**症状**：没有看到任何 [soul] 日志

**解决**：
```bash
# 检查插件目录
ls ~/.hermes/plugins/soul-context-injector/

# 检查 Python 语法
cd ~/.hermes/plugins/soul-context-injector
python3 -m py_compile plugin.py
```

### 问题：Ollama 连接失败

**症状**：日志显示 "Ollama 调用失败"

**解决**：
```bash
# 检查 Ollama 服务
curl http://localhost:11434/api/tags

# 如果未运行
ollama serve

# 检查模型是否下载
ollama list
```

**降级模式**：Ollama 不可用时自动使用本地规则分析，不影响基本功能。

### 问题：规则未加载

**症状**：上下文长度为 0

**解决**：
```bash
# 检查规则文件
ls ~/.hermes/plugins/soul-context-injector/rules/

# 检查索引文件
cat ~/.hermes/plugins/soul-context-injector/rules/index.json
```

### 问题：Hook 未触发

**症状**：消息没有被处理

**解决**：
```bash
# 确认 Hermes 版本支持 Plugin Hook
hermes --version  # 需要 >= 2.0

# 检查插件注册
# plugin.py 末尾必须有 register() 函数
grep "def register" ~/.hermes/plugins/soul-context-injector/plugin.py
```

## 自定义规则

### 添加新规则

1. 创建规则文件：
```bash
vim ~/.hermes/plugins/soul-context-injector/rules/my_rule.md
```

2. 更新索引：
```bash
vim ~/.hermes/plugins/soul-context-injector/rules/index.json
```

添加：
```json
{
  "rule_categories": {
    "my_rule": {"files": ["my_rule.md"]}
  }
}
```

3. 在 `plugin.py` 中添加检测逻辑

### 修改任务等级关键词

编辑 `plugin.py` 中的 `LocalRuleClient.TASK_KEYWORDS`：

```python
TASK_KEYWORDS = {
    "L0": ["几点", "时间", "日期", ...],  # 添加你的关键词
    "L1": ["查看", "读取", ...],
    ...
}
```

## 性能优化

### 缓存规则文件

规则文件使用 `@lru_cache` 缓存，最多缓存 50 个文件。

### Ollama 超时

默认 15 秒超时，可根据网络情况调整：

```yaml
# PLUGIN.yaml
config:
  timeout_ms: 30000  # 30秒
```

## 与 OpenClaw 版本的差异

| 功能 | OpenClaw | Hermes v3.1 |
|------|----------|-------------|
| 消息拦截 | `message_received` | `pre_llm_call` |
| 上下文注入 | 修改 `event.content` | 返回 `context` |
| 工具拦截 | `before_tool_call` | `pre_tool_call` |
| 拦截架构 | 一刀切 | **两层拦截** |
| 破坏性命令 | 拦截 | **永久禁止** |
| 增删改命令 | 拦截 | **L3 认证** |
| 查询命令 | 拦截 | **不处理** |
| L3 认证 | 无 | 有 |
| 认证有效期 | N/A | 1小时 |
| 运行环境 | 仅 Gateway | CLI + Gateway |
| 违规记录 | corrections.md | soul-violations.log |

**v3.1 核心改进：**
- 两层拦截：破坏性禁止 + 增删改认证
- 查询类不处理，减少负担
- 字典扩展：20 条破坏性 + 66 条增删改

**v4.0.0 核心改进：**
- 移除熔断机制，简化架构
- 新增 L4 任务等级（规划任务）
- 修正技能绑定逻辑
- 规划文档自动生成

## 日志级别

设置环境变量控制日志：

```bash
export SOUL_LOG_LEVEL=DEBUG  # 详细日志
export SOUL_LOG_LEVEL=INFO   # 正常日志
export SOUL_LOG_LEVEL=WARN   # 仅警告
```

## 更多信息

- 完整文档：`README.md`
- 规则说明：`rules/trigger_conditions.md`
- 源代码：`plugin.py`
