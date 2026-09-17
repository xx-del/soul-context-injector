"""Ollama 调用参数速度守卫测试"""
import importlib
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def fresh_constants():
    import soul_context_injector.constants as mod
    importlib.reload(mod)
    return mod


class TestOllamaCallOptions:
    """判定调用必须用小上下文、短输出、零温度、无思考"""

    def _call_options(self):
        import soul_context_injector.analyzer as mod
        with patch.object(mod.requests, "post") as mock_post:
            resp = MagicMock()
            resp.json.return_value = {"response": "{}"}
            mock_post.return_value = resp
            mod.call_ollama("hi", model="m", timeout=1.0)
            return mock_post.call_args[1]["json"]["options"]

    def test_num_ctx_is_4096(self):
        assert self._call_options()["num_ctx"] == 4096

    def test_num_predict_capped(self):
        assert self._call_options()["num_predict"] == 150

    def test_temperature_zero(self):
        assert self._call_options()["temperature"] == 0

    def test_think_disabled(self):
        assert self._call_options()["think"] is False


class TestTimeoutDefaults:
    """超时重试默认值收紧"""

    def test_timeout_default_8s(self, monkeypatch, fresh_constants):
        monkeypatch.setattr(
            "soul_context_injector.constants.load_plugin_config", lambda: {}
        )
        assert fresh_constants.load_plugin_config() == {}
        monkeypatch.setattr("yaml.safe_load", lambda *a, **k: {})
        importlib.reload(fresh_constants)
        assert fresh_constants.TIMEOUT_MS == 8000

    def test_retry_default_1(self, fresh_constants):
        assert fresh_constants.MAX_RETRIES == 1
