import os
import google.generativeai as genai
from openai import OpenAI
from abc import ABC, abstractmethod
from typing import List, Dict, Iterator, Optional

class LLMProvider(ABC):
    @abstractmethod
    def generate_stream(self, prompt: str) -> Iterator[str]:
        pass

class GeminiProvider(LLMProvider):
    def __init__(self):
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY not set")
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(
            model_name=os.getenv("GEMINI_MODEL", "gemini-2.0-flash-lite")
        )

    def generate_stream(self, prompt: str) -> Iterator[str]:
        response = self.model.generate_content(prompt, stream=True)
        for chunk in response:
            if chunk.text:
                yield chunk.text

class OpenAIProvider(LLMProvider):
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY not set")
        self.model_name = os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")
        self.api_url = "https://api.openai.com/v1/chat/completions"

    def generate_stream(self, prompt: str) -> Iterator[str]:
        import requests
        import json
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        data = {
            "model": self.model_name,
            "messages": [{"role": "user", "content": prompt}],
            "stream": True
        }
        
        try:
            response = requests.post(self.api_url, headers=headers, json=data, stream=True, timeout=30)
            response.raise_for_status()
            
            for line in response.iter_lines():
                if line:
                    line_text = line.decode('utf-8')
                    if line_text.startswith("data: ") and line_text != "data: [DONE]":
                        json_str = line_text[6:]  # Skip "data: "
                        try:
                            chunk = json.loads(json_str)
                            if 'choices' in chunk and len(chunk['choices']) > 0:
                                content = chunk['choices'][0]['delta'].get('content')
                                if content:
                                    yield content
                        except json.JSONDecodeError:
                            pass
        except Exception as e:
            raise RuntimeError(f"OpenAI API request failed: {str(e)}")


# --- Factory ---
class LLMFactory:
    @staticmethod
    def create_provider(provider_type: str) -> LLMProvider:
        if provider_type.lower() == "gemini":
            return GeminiProvider()
        elif provider_type.lower() == "openai":
            return OpenAIProvider()
        else:
            raise ValueError(f"Unknown provider: {provider_type}")

# --- Service with Fallback ---
class LLMService:
    """
    Service for LLM operations with fallback support.
    """
    
    def __init__(self):
        self.init_errors = []
        
        # Primary Provider
        try:
            self.primary = LLMFactory.create_provider("gemini")
        except Exception as e:
            print(f"Failed to init Gemini: {e}")
            self.init_errors.append(f"Gemini Init Error: {str(e)}")
            self.primary = None

        # Fallback Provider
        try:
            self.fallback = LLMFactory.create_provider("openai")
        except Exception as e:
            print(f"Failed to init OpenAI: {e}")
            self.init_errors.append(f"OpenAI Init Error: {str(e)}")
            self.fallback = None

    def generate_response(self, prompt: str) -> Iterator[str]:
        """
        Generates a response using the primary provider, falling back if necessary.
        """
        runtime_errors = []

        # Try Primary (Gemini)
        if self.primary:
            try:
                yield from self.primary.generate_stream(prompt)
                return
            except Exception as e:
                error = f"Primary LLM (Gemini) runtime error: {str(e)}"
                print(error)
                runtime_errors.append(error)
        
        # Try Fallback (OpenAI)
        if self.fallback:
            try:
                yield from self.fallback.generate_stream(prompt)
                return
            except Exception as e:
                error = f"Fallback LLM (OpenAI) runtime error: {str(e)}"
                print(error)
                runtime_errors.append(error)
        
        # If we get here, everything failed. Return detailed errors.
        error_msg = "Error: All LLM services are currently unavailable.\n\nInitialization Errors:\n"
        if self.init_errors:
            error_msg += "\n".join(self.init_errors)
        else:
            error_msg += "None"
            
        error_msg += "\n\nRuntime Errors:\n"
        if runtime_errors:
            error_msg += "\n".join(runtime_errors)
        else:
            error_msg += "None (Providers failed to initialize)"
            
        yield error_msg


    def generate(self, prompt: str) -> Iterator[str]:
        """Alias for generate_response for backward compatibility."""
        yield from self.generate_response(prompt)

    def stream_recommendation(self, user_query: str, courses: List[Dict]) -> Iterator[str]:
        """Stream recommendation in real-time for faster user experience."""
        
        # Format course information for the prompt
        courses_text = "\n\n".join([
            f"Course {i+1}: {course['code']} - {course['name']}\n"
            f"Description: {course['description']}\n"
            f"Keywords: {course['keywords']}\n"
            f"Relevance: {course['similarity']:.2%}"
            for i, course in enumerate(courses)
        ])
        
        prompt = (
            f"You are a university course advisor. A student asked: '{user_query}'\n\n"
            f"Based on this query, here are the most relevant courses:\n\n{courses_text}\n\n"
            f"Provide a helpful, concise recommendation (2-3 paragraphs). "
            f"Explain which course(s) best match their needs and why. "
            f"Be specific and reference course codes when appropriate."
        )
        
        yield from self.generate_response(prompt)
