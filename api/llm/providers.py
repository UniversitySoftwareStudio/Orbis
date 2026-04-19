from collections.abc import Iterator
from typing import Protocol

import google.generativeai as genai
from openai import OpenAI

from rag.config import RAG_LLM_MAX_TOKENS


class LLMProvider(Protocol):
    def stream(self, prompt: str) -> Iterator[str]: ...


class GeminiProvider:
    def __init__(self, model: str, api_key: str) -> None:
        self.model = model
        genai.configure(api_key=api_key)
        self.client = genai.GenerativeModel(model)

    def stream(self, prompt: str) -> Iterator[str]:
        for chunk in self.client.generate_content(
            prompt,
            stream=True,
            generation_config={"max_output_tokens": RAG_LLM_MAX_TOKENS},
        ):
            text = getattr(chunk, "text", "")
            if text:
                yield text


class OpenAICompatProvider:
    def __init__(self, model: str, api_key: str, base_url: str | None = None) -> None:
        self.model = model
        self.client = OpenAI(api_key=api_key, base_url=base_url)

    def stream(self, prompt: str) -> Iterator[str]:
        chunks = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            stream=True,
            max_tokens=RAG_LLM_MAX_TOKENS,
        )
        for chunk in chunks:
            text = chunk.choices[0].delta.content
            if text:
                yield text
