"""集成测试：验证实际 Ollama 在语义版 prompt 下的输出"""
import json
import urllib.request
import pytest
from pathlib import Path

PLUGIN_DIR = Path(__file__).parent.parent.resolve()

# 从 config.yaml 读取配置
import yaml
config_path = Path.home() / ".hermes" / "config.yaml"
with open(config_path) as f:
    config = yaml.safe_load(f)
soul_config = config.get("plugins", {}).get("soul-context-injector", {})
OLLAMA_URL = soul_config.get("ollama_url", "http://localhost:11434/api/generate")
OLLAMA_MODEL = soul_config.get("ollama_model", "qcwind/qwen2.5-7B-instruct-Q4_K_M:latest")


def _call_ollama(prompt_text: str, user_msg: str) -> dict:
    """模拟 call_ollama() 的调用方式"""
    full_prompt = f"{prompt_text}\n\n## 用户消息\n{user_msg}"
    payload = json.dumps({
        "model": OLLAMA_MODEL,
        "prompt": full_prompt,
        "stream": False,
        "options": {"num_ctx": 12288}
    }).encode()
    req = urllib.request.Request(OLLAMA_URL, payload, {"Content-Type": "application/json"})
    resp = json.loads(urllib.request.urlopen(req, timeout=15).read())
    return resp


def _extract_json(text: str) -> dict:
    """从模型输出中提取 JSON（与 parse_decision() 逻辑一致）"""
    js = text.find("{")
    je = text.rfind("}") + 1
    if js >= 0 and je > js:
        try:
            return json.loads(text[js:je])
        except json.JSONDecodeError:
            pass
    return {}


class TestOllamaSemanticPrompt:
    """验证语义版提示词下 Ollama 输出的格式和分类质量"""

    PROMPT_CONTENT = None  # 运行时从文件加载

    @classmethod
    def setup_class(cls):
        prompt_path = PLUGIN_DIR / "prompts" / "ollama_prompt.md"
        assert prompt_path.exists(), "提示词文件不存在"
        cls.PROMPT_CONTENT = prompt_path.read_text(encoding="utf-8")

    def _analyze(self, msg: str) -> dict:
        """直接调用 Ollama 并解析 JSON 结果"""
        assert self.PROMPT_CONTENT, "提示词未加载"
        resp = _call_ollama(self.PROMPT_CONTENT, msg)
        text = resp.get("response", "")
        parsed = _extract_json(text)
        return parsed

    # === 格式验证 ===

    def test_json_format_valid(self):
        """验证 Ollama 返回的 JSON 包含所有必需字段"""
        result = self._analyze("今天天气怎么样")
        required = {"task_level", "workflow_name", "write_operation",
                    "code_guidance", "agent_pool", "self_improving"}
        assert required.issubset(result.keys()), (
            f"缺失字段: {required - set(result.keys())}"
        )

    def test_task_level_in_valid_range(self):
        """task_level 必须是 L0/L1/L2/L3/L4 之一"""
        result = self._analyze("查看文件")
        assert result.get("task_level") in ("L0", "L1", "L2", "L3", "L4"), (
            f"无效 task_level: {result.get('task_level')}"
        )

    # === 分类验证 ===

    def test_simple_query_l1(self):
        """'查看文件内容' → L1"""
        result = self._analyze("查看文件内容")
        assert result.get("task_level") == "L1"

    def test_analysis_query_l2(self):
        """'分析系统架构' → L2"""
        result = self._analyze("分析系统架构")
        assert result.get("task_level") == "L2"

    def test_execute_query_l3(self):
        """'创建配置文件' → L3"""
        result = self._analyze("创建配置文件")
        assert result.get("task_level") == "L3"

    def test_multi_verb_priority(self):
        """'查看日志找出问题' → L2（语义版应理解'找出'的分析意图）"""
        result = self._analyze("查看日志找出问题")
        assert result.get("task_level") == "L2", (
            f"语义版应识别'找出'的分析意图，实际: {result.get('task_level')}"
        )

    def test_english_fix_l3(self):
        """'fix this bug' → L3"""
        result = self._analyze("fix this bug")
        assert result.get("task_level") == "L3", (
            f"语义版应识别英文执行意图，实际: {result.get('task_level')}"
        )
