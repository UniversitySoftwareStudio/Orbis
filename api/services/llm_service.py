import os
import google.generativeai as genai
from typing import List, Dict, Iterator

class LLMService:
    """
    Service for LLM operations (keyword extraction, response generation).
    """
    
    def __init__(self):
        genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
        self.model = genai.GenerativeModel(
            model_name=os.getenv("INTENT_MODEL", "gemini-2.0-flash-lite")
        )

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
        
        try:
            response = self.model.generate_content(prompt, stream=True)
            for chunk in response:
                if chunk.text:
                    yield chunk.text
        except Exception as e:
            print(f"Streaming recommendation failed: {e}")
            yield f"Found {len(courses)} relevant courses for your query. Consider checking {courses[0]['code']} - {courses[0]['name']} as the top match."
