import os
from collections.abc import Iterator

from core.logging import get_logger
from llm.providers import GeminiProvider, LLMProvider, OpenAICompatProvider

SUPPORTED_PROVIDERS = {"gemini", "groq", "openai"}
logger = get_logger(__name__)


class LLMService:
    def __init__(self) -> None:
        self.provider = ""
        self.model_name = ""
        self._client: LLMProvider
        self.reload_from_env()

    @staticmethod
    def _required_env(name: str) -> str:
        value = (os.getenv(name) or "").strip()
        if not value:
            raise RuntimeError(f"Missing required env var: {name}")
        return value

    def reload_from_env(self) -> None:
        provider = (os.getenv("LLM_PROVIDER", "gemini") or "gemini").strip().lower()
        if provider not in SUPPORTED_PROVIDERS:
            raise RuntimeError("Unsupported LLM_PROVIDER. Use one of: gemini, groq, openai")

        if provider == "gemini":
            self.model_name = (os.getenv("GEMINI_MODEL") or "gemini-1.5-flash").strip()
            self._client = GeminiProvider(self.model_name, self._required_env("GEMINI_API_KEY"))
        else:
            if provider == "groq":
                self.model_name = (os.getenv("GROQ_MODEL") or "llama3-70b-8192").strip()
                api_key = self._required_env("GROQ_API_KEY")
                base_url = "https://api.groq.com/openai/v1"
            else:
                self.model_name = (os.getenv("OPENAI_MODEL") or "gpt-4o-mini").strip()
                api_key = self._required_env("OPENAI_API_KEY")
                base_url = (os.getenv("OPENAI_BASE_URL") or "").strip() or None
            self._client = OpenAICompatProvider(self.model_name, api_key, base_url)

        self.provider = provider
        logger.info("LLM provider configured: %s (%s)", self.provider, self.model_name)

    def generate(self, prompt: str) -> Iterator[str]:
        try:
            yield from self._client.stream(prompt)
        except Exception as exc:
            logger.exception("LLM generation failed")
            yield f"[Error: {exc}]"


def get_llm_service() -> LLMService:
    return LLMService()
