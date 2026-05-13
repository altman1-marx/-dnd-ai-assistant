from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Protocol


DEFAULT_BASE_URL = "https://api.openai.com/v1"


class AIProvider(Protocol):
    def generate_text(self, prompt: str) -> str:
        ...


@dataclass(frozen=True)
class AIProviderConfig:
    api_key: str
    model: str
    base_url: str = DEFAULT_BASE_URL


class MockProvider:
    def __init__(self, response_text: str) -> None:
        self.response_text = response_text

    def generate_text(self, prompt: str) -> str:
        return self.response_text


class OpenAICompatibleProvider:
    def __init__(
        self,
        config: AIProviderConfig,
        opener: Callable[[urllib.request.Request, int], object] | None = None,
        timeout: int = 60,
    ) -> None:
        if not config.api_key.strip():
            raise ValueError("DND_AI_API_KEY is required for openai-compatible provider.")
        if not config.model.strip():
            raise ValueError("DND_AI_MODEL or --model is required for openai-compatible provider.")
        self.config = config
        self.opener = opener or urllib.request.urlopen
        self.timeout = timeout

    def generate_text(self, prompt: str) -> str:
        request = urllib.request.Request(
            url=_join_url(self.config.base_url, "/chat/completions"),
            data=json.dumps(self._request_body(prompt)).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.config.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with self.opener(request, timeout=self.timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(_format_http_error(exc.code, detail)) from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"AI provider request failed: {exc.reason}") from exc

        try:
            return payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ValueError("AI provider response did not include choices[0].message.content.") from exc

    def _request_body(self, prompt: str) -> dict:
        return {
            "model": self.config.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.7,
        }


def load_ai_provider_config(
    base_url: str | None = None,
    model: str | None = None,
    env_file: str | Path | None = None,
) -> AIProviderConfig:
    values = _load_env_file(env_file or ".env.local")
    api_key = os.environ.get("DND_AI_API_KEY") or values.get("DND_AI_API_KEY") or ""
    resolved_model = model or os.environ.get("DND_AI_MODEL") or values.get("DND_AI_MODEL") or ""
    resolved_base_url = base_url or os.environ.get("DND_AI_BASE_URL") or values.get("DND_AI_BASE_URL") or DEFAULT_BASE_URL
    return AIProviderConfig(api_key=api_key, model=resolved_model, base_url=resolved_base_url)


def build_provider(
    provider_name: str,
    mock_response_text: str | None = None,
    base_url: str | None = None,
    model: str | None = None,
) -> AIProvider:
    if provider_name == "mock":
        if mock_response_text is None:
            raise ValueError("--mock-response is required when --provider mock is used.")
        return MockProvider(mock_response_text)
    if provider_name == "openai-compatible":
        return OpenAICompatibleProvider(load_ai_provider_config(base_url=base_url, model=model))
    raise ValueError(f"Unsupported AI provider: {provider_name}")


def _load_env_file(path: str | Path) -> dict[str, str]:
    env_path = Path(path)
    if not env_path.exists():
        return {}
    values: dict[str, str] = {}
    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _join_url(base_url: str, path: str) -> str:
    return base_url.rstrip("/") + "/" + path.lstrip("/")


def _format_http_error(status_code: int, detail: str) -> str:
    try:
        payload = json.loads(detail)
        error = payload.get("error", {})
        code = error.get("code")
        message = error.get("message")
        if code or message:
            return f"AI provider request failed with HTTP {status_code}: {code or 'unknown_error'} - {message or ''}".rstrip()
    except json.JSONDecodeError:
        pass
    return f"AI provider request failed with HTTP {status_code}: {detail}"
