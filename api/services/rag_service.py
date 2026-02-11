import json
from typing import Iterator, Dict
from sqlalchemy.orm import Session
from database.repositories.rag_repository import get_rag_repository
from services.embedding_service import get_embedding_service
from services.llm_service import get_llm_service

class RAGService:
    def __init__(self):
        self.embedding_service = get_embedding_service()
        self.repository = get_rag_repository()
        self.llm_service = get_llm_service()

    def _get_router_decision(self, query: str) -> Dict:
        system_prompt = """
        You are a Query Router for a university database. 
        Analyze the user's question and output a JSON object with the best tool to use.
        
        # 1. TOOL: "SQL"
        Use 'sql' ONLY when the user asks for a LIST of items, specific lookups, COUNTS, or COMPARISONS of specific items.
        
        VALID SCHEMA (Strictly follow these allowed values):
        - allowed_types: "course", "web_page"
        - allowed_filters:
          * "code": Exact match. SUPPORTS MULTIPLE! (e.g., "CMPE 351, CMPE 321")
          * "title_like": Partial match. SUPPORTS MULTIPLE! (e.g., "Computer, Database")
          * "type": MUST be one of the allowed_types.
        
        # 2. TOOL: "VECTOR"
        Use 'vector' for everything else: descriptions, "how to" guides, fuzzy questions, or general topics.
        
        CRITICAL RULES FOR VECTOR:
        - Strip conversational filler ("Compare", "Tell me about", "What is").
        - Keep the query in the SAME LANGUAGE as the user (TR -> TR, EN -> EN).
        - Output ONLY keywords.
        
        # EXAMPLES
        - "What is CMPE 101?" 
          -> { "tool": "sql", "filters": { "type": "course", "code": "CMPE 101" } }
           
        - "Compare CMPE 351 and 321"  <-- UPDATED: Now uses SQL for precision
          -> { "tool": "sql", "filters": { "type": "course", "code": "CMPE 351, CMPE 321" } }
           
        - "List courses about database or network" 
          -> { "tool": "sql", "filters": { "type": "course", "title_like": "Database, Network" } }
           
        - "Show me the announcements" 
          -> { "tool": "sql", "filters": { "type": "web_page", "title_like": "Announcement" } }
          
        - "How is the campus life?"
          -> { "tool": "vector", "query": "campus life social activities" }
          
        - (TR) "Bilgisayar mühendisliği hakkında bilgi ver"
          -> { "tool": "vector", "query": "Bilgisayar mühendisliği genel bilgi" }

        OUTPUT JSON ONLY. NO MARKDOWN.
        """
        
        response_text = ""
        # We consume the stream to get the full JSON string
        for chunk in self.llm_service.generate(f"{system_prompt}\nUser: {query}"):
            response_text += chunk
            
        try:
            # Clean markdown if the LLM adds it
            cleaned = response_text.replace("```json", "").replace("```", "").strip()
            return json.loads(cleaned)
        except:
            print("Router failed to parse JSON. Fallback to Vector.")
            return {"tool": "vector", "query": query}

    def process_query(self, query: str, db: Session) -> Iterator[str]:
        """
        Main RAG Pipeline: Router -> Tool -> Generator
        """
        # 1. Router Step
        decision = self._get_router_decision(query)
        print(f"🧠 Router Decision: {decision}")
        
        context_docs = []
        
        # 2. Retrieval Step
        if decision["tool"] == "sql":
            # Try SQL Filter
            docs = self.repository.sql_filter(db, decision["filters"])
            if not docs:
                print("⚠️ SQL returned 0 results. Falling back to Vector.")
                decision["tool"] = "vector" # Switch mode
            else:
                context_docs = docs

        if decision["tool"] == "vector":
            # Vector Search
            q_emb = self.embedding_service.embed_text(decision.get("query", query))
            context_docs = self.repository.vector_search(db, q_emb, limit=25)

        # === 🔍 IMPROVED DEBUG LOGGING ===
        print(f"\n{'='*50}")
        print(f"🧠 RAG DEBUG: '{decision.get('query', query)}'")
        print(f"{'='*50}")
             
        for i, doc in enumerate(context_docs):
            # Get a clean snippet (first 100 chars, remove newlines)
            snippet = (doc.content[:85] + "...") if doc.content else "No content"
            snippet = snippet.replace('\n', ' ').strip()
                 
            # Print clean, formatted output
            print(f"#{i+1:02d} [{doc.type.upper()}] {doc.title}")
            print(f"    └── {snippet}")
                 
        print(f"{'='*50}\n")
        # =================================

        # 3. Generation Step
        
        # A. Build Context with Metadata
        context_parts = []
        for d in context_docs:
            # Start with Title and Content
            doc_str = f"Source ({d.type}): {d.title}\nContent: {d.content}"
            
            # Check for metadata (handle 'metadata_' or 'metadata')
            meta = getattr(d, "metadata_", getattr(d, "metadata", {})) or {}
            
            if meta:
                # Add useful attributes like ECTS, Code, etc.
                # Filter out complex nested dicts (like weekly schedules) to save tokens
                meta_str = "\nAttributes: " + ", ".join(
                    f"{k.upper()}: {v}" 
                    for k, v in meta.items() 
                    if v and isinstance(v, (str, int, float))
                )
                doc_str += meta_str
            
            context_parts.append(doc_str)
            
        context_str = "\n\n".join(context_parts)

        # B. Construct the Final Prompt
        # This was the missing piece! We need to combine instruction + context + query.
        final_prompt = f"""
        You are a helpful academic assistant for a university.
        
        # INSTRUCTIONS
        1. Use the provided context to answer the user's question accurately.
        2. If the answer is not in the context, say "I don't have that information." or "I don't have information about <topic>" with <topic> being the topic of user query.
        3. **FORMATTING:** Use Markdown to make the answer readable (bold keys, bullet points, tables where appropriate).
        4. **NATURAL LANGUAGE:** Do not simply repeat raw metadata keys like "THEORYPRACTICE_HOUR". Translate them into natural language (e.g., "3 hours theory, 2 hours practice").
        
        ### USER QUESTION:
        {query}

        ### CONTEXT:
        {context_str}
        
        ### ANSWER:
        """
        
        # C. Send to LLM
        yield from self.llm_service.generate(final_prompt)