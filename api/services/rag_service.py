import json
from typing import Iterator, Dict
from sqlalchemy.orm import Session
from database.repositories.rag_repository import get_rag_repository
from services.embedding_service import get_embedding_service
from services.llm_service import get_llm_service
from services.reranker_service import get_reranker_service
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich import box

console = Console()

class RAGService:
    def __init__(self):
        self.embedding_service = get_embedding_service()
        self.repository = get_rag_repository()
        self.llm_service = get_llm_service()
        self.reranker = get_reranker_service()

    def _get_router_decision(self, query: str) -> Dict:
        system_prompt = """
        You are a Query Router for a university database. 
        Analyze the user's question and output a JSON object containing a LIST of "intents".
        
        STRUCTURE:
        {
          "intents": [
            { "tool": "vector", "query": "..." },
            { "tool": "sql", "filters": { "code": "...", "type": "course" } }
          ]
        }
        
        CRITICAL RULES:
        1. **AVAILABLE TOOLS:** "vector", "sql"
        2. **ALLOWED TYPES:** "course", "web_page", "pdf".
        3. **FILTER FORMAT:** { "code": "CMPE" }, { "title_like": "Engineering" }.
        
        4. **TYPE FILTERING (RELAXED):**
            - **DO NOT** apply a "type" filter (pdf/web_page) unless the user EXPLICITLY asks for it (e.g., "Show me the PDF", "Check the website").
            - **EXCEPTION:** If the user asks about **Contact Info, Locations, or "About Us"** for Faculties/Departments, use "filters": { "type": "web_page" }.
            - **FOR REGULATIONS/RULES:** Do **NOT** filter. Rules can exist in both PDFs and Web Pages.
            
        5. **SPLIT COMPARISONS:** If comparing X and Y, generate TWO intents.
        
        6. **STRICT INTENT SEPARATION (CRITICAL):**
            - **SQL Usage:** Use SQL **ONLY** if the user searches for:
                - A specific **Course Code** (e.g. "CMPE 351"). Put it in `filters: { "code": "..." }`.
                - A specific **Subject Code** (e.g. "ACC"). Put it in `filters: { "code": "..." }`.
                - A specific **List Request** (e.g. "List all sociology courses").
            - **VECTOR Usage:** Use VECTOR for **EVERYTHING ELSE**.
                - Questions about "Regulations", "Internships" (Staj), "Erasmus", "Prerequisites", "How to...", "Is there a rule...".
                - **NEVER** use SQL for generic topic searches (e.g. "Staj documents", "Ders registration"). 
                - **Reason:** SQL title search is too broad. Use Semantic Vector search for topics.
        
        OUTPUT JSON ONLY.
        """

        response_text = ""
        for chunk in self.llm_service.generate(f"{system_prompt}\nUser: {query}"):
            response_text += chunk
        try:
            result = json.loads(response_text.replace("```json", "").replace("```", "").strip())
            if "intents" not in result:
                return {"intents": [result]}
            return result
        except:
            return {"intents": [{"tool": "vector", "query": query}]}
    
    def _process_single_intent(self, intent: Dict, db: Session, is_parallel: bool = False) -> list:
        tool = intent.get("tool", "vector").lower()
        query_text = intent.get("query", "")
        filters = intent.get("filters", {})
        
        # 1. SQL Path
        if tool == "sql":
            # --- SANITIZATION BLOCK ---
            # Fix LLM mistakes (e.g. {'like': 'CMPE%'} -> 'CMPE')
            clean_filters = {}
            for k, v in filters.items():
                if isinstance(v, dict):
                    # Try to grab the first value, or just ignore it
                    clean_val = next(iter(v.values()), "")
                    # Remove % wildcards if the repo handles them (Repo adds %..%, so we strip)
                    clean_filters[k] = str(clean_val).replace("%", "")
                else:
                    clean_filters[k] = v
            filters = clean_filters
            # --------------------------

            # --- FIX: Auto-Repair "Lazy" Router ---
            # If Router set type='course' but forgot the 'code' filter, 
            # and provided a short query string (e.g. "ACC"), move it to the filter.
            if filters.get("type") == "course" and "code" not in filters and "title_like" not in filters:
                if query_text and len(query_text) < 10:  # Heuristic: Codes are usually short
                    console.log(f"[cyan]🔧 Auto-repairing filter: Moving query '{query_text}' to code filter.[/cyan]")
                    filters["code"] = query_text
                else:
                    # If we can't repair it, switch to Vector to avoid dumping the whole DB
                    console.log("[yellow]⚠️  SQL Course Search is too broad (no code). Switching to Vector.[/yellow]")
                    tool = "vector"

            # FIX: Force type='course' if searching by code
            # This prevents "Accommodation" (PDF) or "Accounting" (Web) from appearing
            if "code" in filters:
                filters["type"] = "course"

            # If the router picked SQL but didn't give filters, it's a hallucination.
            # Switch to Vector to prevent dumping the whole database.
            if not filters:
                console.log("[yellow]⚠️  SQL Intent has no filters. Switching to Vector.[/yellow]")
                tool = "vector"
                # Ensure we have a query string for the vector search
                if not query_text and intent.get("query"):
                    query_text = intent.get("query")
            else:
                # Only run SQL if filters exist
                console.log(f"[bold blue]🔍 SQL Search:[/bold blue] {filters}")
                limit = 75
                docs = self.repository.sql_filter(db, filters, limit=limit)
                if docs: 
                    return docs
                
                console.log("[yellow]   SQL returned 0. Switching to Vector.[/yellow]")
                tool = "vector" # Fallback
                
                if not query_text:
                    query_text = " ".join([str(v) for k,v in filters.items() if v])

        # 2. Vector Path
        if tool == "vector":
            # --- Dynamic Throttling ---
            # If parallel, be conservative to save tokens
            search_limit = 15 if is_parallel else 30
            
            # Skip if query is still empty
            if not query_text.strip():
                return []

            console.log(f"[bold magenta]🔍 Vector Search:[/bold magenta] '{query_text}' (Limit: {search_limit})")
            if filters:
                console.log(f"[dim]   Applying Filters: {filters}[/dim]")
            
            q_emb = self.embedding_service.embed_text(query_text)
            
            # A. Initial Retrieval (Hybrid: Vector + Keyword)
            initial_docs = self.repository.vector_search(
                db, 
                query_embedding=q_emb, 
                query_text=query_text, # Pass the raw text for keyword boosting
                filters=filters, 
                limit=search_limit
            )
            
            if not initial_docs:
                return []

            # =========================================================
            # Pre-Expansion Rerank
            # =========================================================
            # We assume 'initial_docs' contains the raw search results (e.g. 40 docs).
            # We RERANK them NOW to find the "True Top 3" before we waste time expanding the wrong ones.
            
            # Construct text for Reranker
            rerank_texts = []
            for d in initial_docs:
                meta = getattr(d, "metadata_", getattr(d, "metadata", {})) or {}
                clean_meta = ", ".join([f"{k}: {v}" for k, v in meta.items() if isinstance(v, (str, int, float))])
                text_block = (
                    f"Title: {d.title}\n"
                    f"URL: {getattr(d, 'url', 'N/A')}\n"
                    f"Content: {d.content}"
                )
                rerank_texts.append(text_block)

            # Rerank the initial pool
            if len(initial_docs) > 0:
                console.log(f"   ⚖️  Pre-Expansion Reranking {len(initial_docs)} candidates...")
                pre_rerank_results = self.reranker.rerank(
                    query=query_text,
                    documents=rerank_texts,
                    top_k=len(initial_docs) # Reorder all of them
                )
                
                # Reconstruct list in new order
                reranked_initial_docs = []
                for res in pre_rerank_results:
                    reranked_initial_docs.append(initial_docs[res["index"]])
            else:
                reranked_initial_docs = initial_docs

            # =========================================================
            # Smart Expansion (Using True Top 3)
            # =========================================================
            # Now we pick the top 3 from the *RERANKED* list.
            
            docs_to_expand = reranked_initial_docs[:3]
            
            expanded_docs_map = {}
            
            # 1. Add top 10 reranked docs to the map immediately (High Relevance Baseline)
            for d in reranked_initial_docs[:10]:
                expanded_docs_map[d.id] = d

            # 2. Identify URLs to expand from the Top 3
            unique_urls = []
            seen_urls = set()
            
            for d in docs_to_expand:
                url = getattr(d, "url", None)
                if d.type in ['web_page', 'pdf'] and url and url not in seen_urls:
                    unique_urls.append(url)
                    seen_urls.add(url)

            # 3. Perform Expansion Fetch
            if unique_urls:
                console.log(f"   🔄 Expanding {len(unique_urls)} source(s)...")
                
                # Print titles being expanded
                for url in unique_urls:
                    matching_doc = next((d for d in docs_to_expand if getattr(d, 'url', None) == url), None)
                    safe_title = getattr(matching_doc, 'title', 'Untitled') if matching_doc else "Unknown Source"
                    console.log(f"      - [dim cyan]{safe_title}[/dim cyan]")

                for url in unique_urls:
                    page_chunks = self.repository.get_by_url(db, url)
                    for chunk in page_chunks:
                        if chunk.id not in expanded_docs_map:
                            expanded_docs_map[chunk.id] = chunk
            
            candidate_docs = list(expanded_docs_map.values())

            # =========================================================
            # Final Rerank (The Context Optimizer)
            # =========================================================
            RERANK_INPUT_CAP = 75
            
            if len(candidate_docs) > RERANK_INPUT_CAP:
                console.log(f"[yellow]⚠️  Too many chunks ({len(candidate_docs)}). Capping at {RERANK_INPUT_CAP} for final reranking.[/yellow]")
                
                # Intelligent Slicing:
                # Prioritize the docs that triggered the expansion (Top 3 Reranked)
                priority_ids = {d.id for d in docs_to_expand}
                priority_docs = [d for d in candidate_docs if d.id in priority_ids]
                other_docs = [d for d in candidate_docs if d.id not in priority_ids]
                
                # Fill the rest
                slots_left = RERANK_INPUT_CAP - len(priority_docs)
                candidate_docs = priority_docs + other_docs[:slots_left]

            # Final Reranking
            if candidate_docs:
                console.log(f"   ⚖️  Final Reranking {len(candidate_docs)} chunks...")
                doc_texts = []
                for d in candidate_docs:
                    # Safely extract metadata
                    meta = getattr(d, "metadata_", getattr(d, "metadata", {})) or {}
                    clean_meta = ", ".join([f"{k}: {v}" for k, v in meta.items() if isinstance(v, (str, int, float))])
                    
                    # Construct a rich text block for the Reranker
                    text_for_reranker = (
                        f"Title: {d.title}\n"
                        f"URL: {getattr(d, 'url', 'N/A')}\n"
                        f"Language: {getattr(d, 'language', 'N/A')}\n"
                        f"Metadata: {clean_meta}\n"
                        f"Content: {d.content}"
                    )
                    doc_texts.append(text_for_reranker)
                
                reranked_results = self.reranker.rerank(
                    query=query_text, 
                    documents=doc_texts, 
                    top_k=5 if is_parallel else 10 
                )
                
                final_docs = []
                for res in reranked_results:
                    original_doc = candidate_docs[res["index"]]
                    original_doc.score = res['score']
                    final_docs.append(original_doc)
                return final_docs
                
        return []

    def process_query(self, query: str, db: Session) -> Iterator[str]:
        # 1. Router Step
        router_decision = self._get_router_decision(query)
        intents = router_decision.get("intents", [])
        
        # VISUALIZATION
        router_display = "\n".join([f"{i+1}. [{x['tool'].upper()}] {x.get('query') or x.get('filters')}" for i, x in enumerate(intents)])
        console.print(Panel(router_display, title=f"🧠 Router: {len(intents)} Intent(s)", border_style="cyan", box=box.SIMPLE))

        all_context_docs = []
        is_parallel = len(intents) > 1

        # 2. Parallel Execution Loop
        for i, intent in enumerate(intents):
            console.rule(f"[bold]Processing Intent #{i+1}[/bold]")
            intent_docs = self._process_single_intent(intent, db, is_parallel=is_parallel)
            all_context_docs.extend(intent_docs)

        # 3. Deduplication
        unique_map = {}
        for d in all_context_docs:
            if d.id not in unique_map:
                unique_map[d.id] = d
        
        context_docs = list(unique_map.values())
        
        # VISUALIZATION: Final Table
        table = Table(title=f"Final Merged Context ({len(context_docs)} Docs)", box=box.SIMPLE)
        table.add_column("Score", style="magenta", width=6)
        table.add_column("Type", style="cyan", width=10)
        table.add_column("Title", style="green")
        table.add_column("Snippet", style="white", no_wrap=True)

        for doc in context_docs:
            score = f"{doc.score:.3f}" if hasattr(doc, 'score') else "-" 
            snippet = (doc.content[:60].replace('\n', ' ') + "...") if doc.content else ""
            table.add_row(score, doc.type.upper(), doc.title, snippet)
        console.print(table)
        console.print("\n")

        # 4. Context Building (Restored CSV Logic)
        if not context_docs:
            console.log("⚠️ No relevant documents found.")
            yield "I'm sorry, but I couldn't find any specific information."
            return

        context_str = ""
        
        # FIX: Check if any intent was SQL-based (since 'decision' variable no longer exists)
        has_sql_intent = any(intent.get("tool", "").lower() == "sql" for intent in intents)

        # Only compact if it is an SQL search (structured data) OR if we have too many docs for text
        is_sql_list = (has_sql_intent and len(context_docs) > 5)
        is_massive_vector = (len(context_docs) > 40)

        if is_sql_list or is_massive_vector:
            # ... (Existing CSV Logic) ...
            course_count = sum(1 for d in context_docs if d.type == 'course')
            is_course_list = course_count > (len(context_docs) / 2)
            
            if is_course_list:
                console.log("[green]📋 Detected Course List. Compacting to CSV...[/green]")
                context_str = "The user asked for a list of courses. CSV Format:\n\nID, Code, Title, ECTS, Info\n"
                for d in context_docs:
                    meta = getattr(d, "metadata_", getattr(d, "metadata", {})) or {}
                    code = meta.get("course_code", "N/A")
                    ects = meta.get("ects", "-")
                    snippet = (d.content[:50].replace("\n", " ") + "...") if d.content else ""
                    context_str += f"{d.id}, {code}, {d.title}, {ects}, {snippet}\n"
            else:
                console.log("[green]📋 Detected General List. Compacting to CSV...[/green]")
                context_str = "The user asked for a list. CSV Format:\n\nID, Type, Title, URL, Snippet\n"
                for d in context_docs:
                    meta = getattr(d, "metadata_", getattr(d, "metadata", {})) or {}
                    url = getattr(d, "url", "N/A")
                    source_ref = url if d.type == 'web_page' else meta.get("course_code", "N/A")
                    snippet = (d.content[:100].replace("\n", " ") + "...") if d.content else ""
                    context_str += f"{d.id}, {d.type}, {d.title}, {source_ref}, {snippet}\n"
        else:
            # Standard detailed context for Vector Search
            context_parts = []
            for d in context_docs:
                # Explicitly label the URL for the LLM
                source_url = getattr(d, "url", "N/A")
                
                doc_str = f"Source: {d.title}\nURL: {source_url}\nContent: {d.content}"
                
                meta = getattr(d, "metadata_", getattr(d, "metadata", {})) or {}
                if meta:
                    clean_meta = {k: v for k, v in meta.items() if isinstance(v, (str, int, float))}
                    meta_str = "\nAttributes: " + ", ".join(f"{k.upper()}: {v}" for k, v in clean_meta.items())
                    doc_str += meta_str
                context_parts.append(doc_str)
            context_str = "\n\n".join(context_parts)

        # 5. Generation
        final_prompt = f"""
        You are a knowledgeable and helpful academic assistant for Istanbul Bilgi University.
        
        # INSTRUCTIONS
        1. **TONE:** Be confident, direct, and friendly.
        2. **ACCURACY:** Answer using ONLY the provided context.
        3. **FORMAT:** Use Markdown (headers, bullet points, bold text). If you are given a list (CSV data), you can present it nicely instead of directly copy-pasting it.
        
        4. **CITATION PROTOCOL (CRITICAL):**
            - **Rule 1 (Entities):** When mentioning an office, role, or department (e.g. Erasmus Office, Coordinator), use **Bold Text** only. Do NOT link them.
            - **Rule 2 (Sources):** Cite the document where you found the information using a Markdown link on the Title.
                - *Example:* "Details are in the [Study Mobility Guide](url)."
            - **Rule 3 (Linking):** Create a Markdown link on the *Document Title* itself.
                - *Bad:* "Contact the [Erasmus Office](url)..." (Don't link the entity)
                - *Good:* "Contact the **Erasmus Office**, as stated in the [Study Mobility Guide](url)." (Link the source)
            - **Rule 4 (Lists):** If providing a list of courses (CSV data), **DO NOT** try to cite a "Course Catalog" or "Website" unless a URL is explicitly provided in the text. Just present the list accordingly.
            - **Rule 5 (Fallback):** If no URL is provided for a document, just write its title in *Italics*.
        
        5. **DYNAMIC SAFETY:**
            - If the answer involves administrative procedures, identify the **correct authority** mentioned in the text (e.g., **Student Affairs**) and advise contacting them.
        
        ### USER QUESTION:
        {query}

        ### CONTEXT:
        {context_str}
        
        ### ANSWER:
        """

        yield from self.llm_service.generate(final_prompt)