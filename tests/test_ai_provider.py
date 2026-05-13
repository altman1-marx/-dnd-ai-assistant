import json
import http.client
import tempfile
import unittest
import urllib.error
from pathlib import Path

from dnd_ai_assistant.ai_provider import (
    AIProviderConfig,
    MockProvider,
    OpenAICompatibleProvider,
    build_provider,
    load_ai_provider_config,
)


class FakeResponse:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


class FakeErrorBody:
    def __init__(self, text: str) -> None:
        self.text = text

    def read(self) -> bytes:
        return self.text.encode("utf-8")


class AIProviderTests(unittest.TestCase):
    def test_mock_provider_returns_fixed_text(self) -> None:
        provider = MockProvider("hello")

        self.assertEqual(provider.generate_text("prompt"), "hello")

    def test_openai_compatible_provider_builds_chat_completion_request(self) -> None:
        captured = {}

        def opener(request, timeout):
            captured["url"] = request.full_url
            captured["timeout"] = timeout
            captured["body"] = json.loads(request.data.decode("utf-8"))
            captured["authorization"] = request.headers["Authorization"]
            return FakeResponse({"choices": [{"message": {"content": "model output"}}]})

        provider = OpenAICompatibleProvider(
            AIProviderConfig(api_key="secret", model="test-model", base_url="https://example.test/v1"),
            opener=opener,
            timeout=12,
            response_format="json_object",
        )

        output = provider.generate_text("Build an adventure.")

        self.assertEqual(output, "model output")
        self.assertEqual(captured["url"], "https://example.test/v1/chat/completions")
        self.assertEqual(captured["timeout"], 12)
        self.assertEqual(captured["body"]["model"], "test-model")
        self.assertEqual(captured["body"]["response_format"], {"type": "json_object"})
        self.assertEqual(captured["body"]["messages"][0]["content"], "Build an adventure.")
        self.assertEqual(captured["authorization"], "Bearer secret")

    def test_openai_compatible_provider_requires_key_and_model(self) -> None:
        with self.assertRaises(ValueError):
            OpenAICompatibleProvider(AIProviderConfig(api_key="", model="test-model"))
        with self.assertRaises(ValueError):
            OpenAICompatibleProvider(AIProviderConfig(api_key="secret", model=""))

    def test_openai_compatible_provider_formats_json_http_errors(self) -> None:
        def opener(request, timeout):
            error_body = json.dumps({"error": {"code": "insufficient_quota", "message": "Quota exceeded."}})
            raise urllib.error.HTTPError(
                request.full_url,
                429,
                "Too Many Requests",
                {},
                FakeErrorBody(error_body),
            )

        provider = OpenAICompatibleProvider(
            AIProviderConfig(api_key="secret", model="test-model", base_url="https://example.test/v1"),
            opener=opener,
        )

        with self.assertRaisesRegex(RuntimeError, "insufficient_quota"):
            provider.generate_text("prompt")

    def test_openai_compatible_provider_formats_incomplete_reads(self) -> None:
        def opener(request, timeout):
            raise http.client.IncompleteRead(b"")

        provider = OpenAICompatibleProvider(
            AIProviderConfig(api_key="secret", model="test-model", base_url="https://example.test/v1"),
            opener=opener,
        )

        with self.assertRaisesRegex(RuntimeError, "complete JSON body"):
            provider.generate_text("prompt")

    def test_load_ai_provider_config_reads_env_file_without_printing_key(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / ".env.local"
            path.write_text(
                "DND_AI_API_KEY=secret\nDND_AI_MODEL=test-model\nDND_AI_BASE_URL=https://example.test/v1\n",
                encoding="utf-8",
            )

            config = load_ai_provider_config(env_file=path)

        self.assertEqual(config.api_key, "secret")
        self.assertEqual(config.model, "test-model")
        self.assertEqual(config.base_url, "https://example.test/v1")

    def test_load_ai_provider_config_handles_utf8_bom_env_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / ".env.local"
            path.write_text(
                "DND_AI_API_KEY=secret\nDND_AI_MODEL=test-model\n",
                encoding="utf-8-sig",
            )

            config = load_ai_provider_config(env_file=path)

        self.assertEqual(config.api_key, "secret")
        self.assertEqual(config.model, "test-model")

    def test_build_provider_requires_mock_response_for_mock_provider(self) -> None:
        with self.assertRaises(ValueError):
            build_provider("mock")


if __name__ == "__main__":
    unittest.main()
