#!/bin/bash
# 重启后运行时闭环验证（需网关已重启且配置已手动改好）
# 退出码：0 全过，非 0 有未达项
set -u
FAIL=0

echo "=== 1. slim 无注入 ==="
if grep -a "injected skill-slimmer" ~/.hermes/logs/agent.log 2>/dev/null | grep -a "$(date +%Y-%m-%d)" | grep -aq "L1 injected"; then
  echo "FAIL: 仍有 slim L1 全文注入"; FAIL=1
else
  echo "PASS: 当日无 slim L1 注入"
fi

echo "=== 2. external_dirs 为空 ==="
if grep -a -A 2 "^skills:" ~/.hermes/config.yaml | grep -aq "external_dirs: \[\]"; then
  echo "PASS: external_dirs 为空"
else
  echo "FAIL: external_dirs 非空"; FAIL=1
fi

echo "=== 3. local_knowledge 索引覆盖外部库 ==="
if grep -a -A 2 "local_knowledge:" ~/.hermes/config.yaml | grep -aq "Anthropic-Cybersecurity-Skills"; then
  echo "PASS: 索引覆盖已配置"
else
  echo "FAIL: 索引覆盖缺失"; FAIL=1
fi

echo "=== 4. 系统提示无外部索引残留（抽查最新会话） ==="
echo "INFO: 需人工确认新会话系统提示无 Skills 外部大段列表"

exit $FAIL
