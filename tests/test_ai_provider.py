import json
import tempfile
import unittest
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
        )

        output = provider.generate_text("Build an adventure.")

        self.assertEqual(output, "model output")
        self.assertEqual(captured["url"], "https://example.test/v1/chat/completions")
        self.assertEqual(captured["timeout"], 12)
        self.assertEqual(captured["body"]["model"], "test-model")
        self.assertEqual(captured["body"]["messages"][0]["content"], "Build an adventure.")
        self.assertEqual(captured["authorization"], "Bearer secret")

    def test_openai_compatible_provider_requires_key_and_model(self) -> None:
        with self.assertRaises(ValueError):
            OpenAICompatibleProvider(AIProviderConfig(api_key="", model="test-model"))
        with self.assertRaises(ValueError):
            OpenAICompatibleProvider(AIProviderConfig(api_key="secret", model=""))

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

    def test_build_provider_requires_mock_response_for_mock_provider(self) -> None:
        with self.assertRaises(ValueError):
            build_provider("mock")


if __name__ == "__main__":
    unittest.main()
