import os
from openai import OpenAI
import google.generativeai as genai

class LLMService:
    def __init__(self):
        self.provider = os.getenv("LLM_PROVIDER", "gemini")
        self.client = None
        
        if self.provider == "groq":
            # Groq uses the OpenAI client structure!
            self.client = OpenAI(
                base_url="https://api.groq.com/openai/v1",
                api_key=os.getenv("GROQ_API_KEY")
            )
            self.model_name = os.getenv("GROQ_MODEL", "llama3-70b-8192")
            print(f"✅ LLM Service initialized with Groq (Model: {self.model_name})")
            
        elif self.provider == "gemini":
            genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
            self.model_name = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
            self.client = genai.GenerativeModel(self.model_name)

    def generate(self, prompt: str):
        """
        Generates text and yields chunks (streaming).
        """
        try:
            if self.provider == "groq":
                stream = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=[{"role": "user", "content": prompt}],
                    stream=True
                )
                for chunk in stream:
                    if chunk.choices[0].delta.content:
                        yield chunk.choices[0].delta.content

            elif self.provider == "gemini":
                response = self.client.generate_content(prompt, stream=True)
                for chunk in response:
                    yield chunk.text

        except Exception as e:
            print(f"❌ LLM Generation Error: {e}")
            yield f"[Error: {str(e)}]"

# Singleton
_service = LLMService()
def get_llm_service():
    return _service