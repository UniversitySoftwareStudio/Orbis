import requests
import os
import json
from typing import List, Dict, Any

class RerankerService:
    def __init__(self):
        self.api_key = os.getenv("JINA_API_KEY")
        self.url = "https://api.jina.ai/v1/rerank"

    def rerank(self, query: str, documents: List[str], top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Calls Jina AI Reranker API.
        """
        # check if key exists (and is not just the example placeholder)
        if not self.api_key or self.api_key.startswith("jina_xxx"):
            print("⚠️ JINA_API_KEY missing or invalid. Skipping reranker.")
            return self._fallback(documents, top_k)

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        payload = {
            "model": "jina-reranker-v2-base-multilingual",
            "query": query,
            "documents": documents,
            "top_n": top_k
        }

        try:
            # Send request
            response = requests.post(self.url, headers=headers, json=payload, timeout=10)
            response.raise_for_status()
            
            # API returns: { "results": [ { "index": 0, "relevance_score": 0.9, ... }, ... ] }
            results = response.json().get("results", [])
            
            formatted_results = []
            for item in results:
                idx = item["index"]
                
                # FIX: Don't parse 'document' from API response. 
                # Use the index to grab the original text from our memory. 
                # This prevents "string indices" errors if API schema changes.
                original_text = documents[idx]
                
                formatted_results.append({
                    "index": idx,
                    "score": item["relevance_score"],
                    "document": original_text
                })
                
            return formatted_results

        except Exception as e:
            print(f"⚠️ Jina Reranker Failed: {e}")
            return self._fallback(documents, top_k)

    def _fallback(self, documents, top_k):
        """Fallback: Return first k docs as-is if API fails"""
        print("   └── Using Vector Search fallback (No Reranking)")
        results = []
        # Return the top k from the original vector search order
        for i, doc in enumerate(documents[:top_k]):
            results.append({
                "index": i, 
                "score": 0.0, 
                "document": doc
            })
        return results

_reranker = RerankerService()
def get_reranker_service():
    return _reranker