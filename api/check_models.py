import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("GOOGLE_API_KEY") # Or GEMINI_API_KEY, whichever you use
if not api_key:
    print("❌ No API Key found in environment variables.")
    exit()

genai.configure(api_key=api_key)

print("🔍 Listing available models for your API Key...")
try:
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods:
            print(f" - {m.name}")
except Exception as e:
    print(f"❌ Error listing models: {e}")