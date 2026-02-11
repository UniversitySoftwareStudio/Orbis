import json
from typing import Iterator, Dict
from sqlalchemy.orm import Session
from database.repositories.rag_repository import get_rag_repository
from services.embedding_service import get_embedding_service
from services.llm_service import get_llm_service
from services.reranker_service import get_reranker_service # <--- New Import

class RAGService:
    def __init__(self):
        self.embedding_service = get_embedding_service()
        self.repository = get_rag_repository()
        self.llm_service = get_llm_service()
        self.reranker = get_reranker_service() # <--- Init Reranker

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
        
        OUTPUT JSON ONLY. NO MARKDOWN.
        """
        # (Router prompt usage unchanged)
        response_text = ""
        for chunk in self.llm_service.generate(f"{system_prompt}\nUser: {query}"):
            response_text += chunk
        try:
            return json.loads(response_text.replace("```json", "").replace("```", "").strip())
        except:
            return {"tool": "vector", "query": query}

    def process_query(self, query: str, db: Session) -> Iterator[str]:
        # 1. Router Step
        decision = self._get_router_decision(query)
        decision["tool"] = decision.get("tool", "").lower()
        print(f"🧠 Router Decision: {decision}")
        
        context_docs = []
        
        # 2. Retrieval Step
        if decision["tool"] == "sql":
            print(f"🔍 Executing SQL Filter: {decision['filters']}")
            limit = 50 if "title_like" in decision["filters"] else 5
            context_docs = self.repository.sql_filter(db, decision["filters"], limit=limit)
            if not context_docs:
                print("⚠️ SQL returned 0 results. Falling back to Vector.")
                decision["tool"] = "vector"

        if decision["tool"] == "vector":
            # A. Initial Retrieval (High Recall, Low Precision)
            q_emb = self.embedding_service.embed_text(decision.get("query", query))
            initial_docs = self.repository.vector_search(db, q_emb, limit=25)
            
            # B. Smart Expansion (Get Top 3 Unique Pages)
            expanded_docs_map = {} # Use dict to deduplicate by ID
            unique_urls = []
            seen_urls = set()
            
            for d in initial_docs:
                url = getattr(d, "url", None)
                # If it's a web page, collect its URL
                if d.type == 'web_page' and url and url not in seen_urls:
                    unique_urls.append(url)
                    seen_urls.add(url)
                    if len(unique_urls) >= 3: # Limit to Top 3 sources
                        break
            
            # Fetch full content for these URLs
            if unique_urls:
                print(f"🔄 Smart Expansion: Fetching full context for {len(unique_urls)} pages...")
                for url in unique_urls:
                    page_chunks = self.repository.get_by_url(db, url)
                    for chunk in page_chunks:
                        expanded_docs_map[chunk.id] = chunk
            
            # Also ensure original non-webpage results (like courses) are kept
            for d in initial_docs:
                if d.type != 'web_page':
                    expanded_docs_map[d.id] = d
            
            # Convert map back to list of candidates
            candidate_docs = list(expanded_docs_map.values())

            # C. Reranking (High Precision)
            if candidate_docs:
                print(f"⚖️ Reranking {len(candidate_docs)} chunks with jina-reranker-v2-base-multilingual...")
                
                # Extract text for reranker
                doc_texts = [d.content for d in candidate_docs]
                
                # Call Microservice (Top 10)
                reranked_results = self.reranker.rerank(
                    query=decision.get("query", query), 
                    documents=doc_texts, 
                    top_k=10
                )
                
                # Map back to objects
                final_context_docs = []
                for res in reranked_results:
                    # Reranker returns indices relative to the list we sent
                    original_doc = candidate_docs[res["index"]]
                    # Optional: Inject the relevance score into metadata for debugging
                    # original_doc.metadata_['relevance_score'] = res['score'] 
                    final_context_docs.append(original_doc)
                    
                context_docs = final_context_docs
                print(f"✅ Kept Top {len(context_docs)} most relevant chunks.")
            else:
                context_docs = []

        # Debug Logging
        print(f"\n{'='*50}\n🧠 RAG DEBUG: '{decision.get('query', query)}'\n{'='*50}")
        for i, doc in enumerate(context_docs):
            snippet = (doc.content[:85] + "...") if doc.content else "No content"
            snippet = snippet.replace('\n', ' ').strip()
            print(f"#{i+1:02d} [{doc.type.upper()}] {doc.title}\n    └── {snippet}")
        print(f"{'='*50}\n")

        # 3. Context Building
        context_str = ""
        # (Same CSV logic as before...)
        if decision["tool"] == "sql" and len(context_docs) > 5:
            # ... CSV Logic ...
            course_count = sum(1 for d in context_docs if d.type == 'course')
            is_course_list = course_count > (len(context_docs) / 2)
            if is_course_list:
                context_str = "The user asked for a list of courses. CSV Format:\n\nID, Code, Title, ECTS, Info\n"
                for d in context_docs:
                    meta = getattr(d, "metadata_", getattr(d, "metadata", {})) or {}
                    code = meta.get("course_code", "N/A")
                    ects = meta.get("ects", "-")
                    snippet = (d.content[:50].replace("\n", " ") + "...") if d.content else ""
                    context_str += f"{d.id}, {code}, {d.title}, {ects}, {snippet}\n"
            else:
                context_str = "The user asked for a list. CSV Format:\n\nID, Type, Title, URL, Snippet\n"
                for d in context_docs:
                    meta = getattr(d, "metadata_", getattr(d, "metadata", {})) or {}
                    url = getattr(d, "url", "N/A")
                    source_ref = url if d.type == 'web_page' else meta.get("course_code", "N/A")
                    snippet = (d.content[:100].replace("\n", " ") + "...") if d.content else ""
                    context_str += f"{d.id}, {d.type}, {d.title}, {source_ref}, {snippet}\n"
        else:
            context_parts = []
            for d in context_docs:
                doc_str = f"Source ({d.type}): {d.title}\nContent: {d.content}"
                meta = getattr(d, "metadata_", getattr(d, "metadata", {})) or {}
                if meta:
                    clean_meta = {k: v for k, v in meta.items() if isinstance(v, (str, int, float))}
                    meta_str = "\nAttributes: " + ", ".join(f"{k.upper()}: {v}" for k, v in clean_meta.items())
                    doc_str += meta_str
                context_parts.append(doc_str)
            context_str = "\n\n".join(context_parts)

        # === 🔧 SAFETY VALVE: If no docs found, don't ask LLM ===
        if not context_docs:
            print("⚠️ No relevant documents found. Returning default response.")
            yield "I'm sorry, but I couldn't find any specific information about that in the university database."
            return
        # ========================================================

        # 4. Generation
        final_prompt = f"""
        You are a helpful academic assistant for a university.
        
        # INSTRUCTIONS
        1. Use the provided context to answer the user's question accurately.
        2. If the answer is not in the context, say "I don't have that information.".
        3. **FORMATTING:** Use Markdown to make the answer readable (bold keys, bullet points).
        4. **NATURAL LANGUAGE:** Translate metadata keys (e.g. "3 hours theory").
        
        ### USER QUESTION:
        {query}

        ### CONTEXT:
        {context_str}
        
        ### ANSWER:
        """
        yield from self.llm_service.generate(final_prompt)