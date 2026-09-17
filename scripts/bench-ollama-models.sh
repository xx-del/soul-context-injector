#!/bin/bash
# 对比候选模型在固定 10 条消息上的耗时与判定正确率
# 用法：bash scripts/bench-ollama-models.sh "qwen3.5:4b" "qcwind/qwen2.5-7B-instruct-Q4_K_M:latest"
# 输出：每模型平均耗时 + 与本地规则期望等级的一致数
#
# 关思考调法（已实测）：
#   CLI 必须用等号形式：ollama run "$model" --think=false "$prompt"
#   空格形式（--think false）会被误解析为提示词前缀，思考关不掉。
#   qwen2.5 系非思考模型接受 --think=false（静默忽略，不报错）。
#   API 等价调法：POST /api/generate {"think": false, "options": {"think": false, ...}}
#
# 期望表：10 条固定消息（L0/L1/L2/L3/L4 各 2 条，取自 tests 现有用例）。
set -u

PROMPT_TMPL='你是任务分级器。只输出JSON：{"task_level": "Lx"}，不要其他内容。分级：L0=简单问答（问候/时间）；L1=只读查询（查看/搜索/列目录）；L2=分析理解评估规划；L3=执行操作（创建/修复/部署）；L4=确认执行已有方案（好的/同意/执行吧）。用户消息：%s'

# msg|expected 交替写死
MSGS=(
  "你好|L0"
  "现在几点了|L0"
  "查看这个文件|L1"
  "查看日志找出问题|L1"
  "分析一下系统架构|L2"
  "我看一下这个对不对|L2"
  "修复bug|L3"
  "实现一个功能|L3"
  "确认|L4"
  "同意|L4"
)

CALL_TIMEOUT=120

bench_model() {
  local model="$1"
  # 预热一次（模型加载耗时不计入平均）
  timeout "$CALL_TIMEOUT" ollama run "$model" --think=false "只输出：ok" >/dev/null 2>&1
  local total_ms=0 match=0 n=0
  echo "=== $model ==="
  for item in "${MSGS[@]}"; do
    local msg="${item%%|*}"
    local expect="${item##*|}"
    local prompt
    prompt=$(printf "$PROMPT_TMPL" "$msg")
    local start end ms out level
    start=$(date +%s%N)
    out=$(timeout "$CALL_TIMEOUT" ollama run "$model" --think=false "$prompt" 2>/dev/null)
    end=$(date +%s%N)
    ms=$(( (end - start) / 1000000 ))
    level=$(printf '%s' "$out" | grep -oE '"task_level"[[:space:]]*:[[:space:]]*"L[0-4]"' | grep -oE 'L[0-4]' | head -n1)
    [ -z "$level" ] && level="?"
    local mark="MISS"
    if [ "$level" = "$expect" ]; then mark="HIT"; match=$((match + 1)); fi
    n=$((n + 1))
    total_ms=$((total_ms + ms))
    echo "[$mark] expect=$expect got=$level ${ms}ms :: $msg"
  done
  local avg=$((total_ms / n))
  echo "--- $model : 平均 ${avg}ms/条，一致 ${match}/${n} ---"
  echo
}

if [ "$#" -lt 1 ]; then
  echo "用法：bash scripts/bench-ollama-models.sh <model1> [model2 ...]" >&2
  exit 1
fi

for m in "$@"; do
  bench_model "$m"
done
