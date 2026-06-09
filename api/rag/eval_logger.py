import json
import os
import uuid
from rag.helpers import doc_meta
from datetime import datetime, timezone
from contextvars import ContextVar

rag_eval_state: ContextVar[dict] = ContextVar('rag_eval_state', default={})

EVAL_FILE_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "rag_evaluation_logs.jsonl")

def init_eval_state(query: str) -> None:
    state = {
        "query_metadata": {
            "query_id": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "user_query": query
        },
        "routing_phase": {"router_decision": {}},
        "retrieval_and_reranking_phase": {
            "parallel_searches": [],
            "smart_expansion": {"triggered": False, "expanded_pdf_ids": [], "newly_added_chunk_ids": []},
            "second_reranking_final_order_ids": []
        },
        "formatting_phase": {"csv_compacting": {"triggered": False, "items_compacted": 0}},
        "generation_phase": {"final_response": "", "context_token_count": 0},
        "chunk_metadata_dictionary": {} # Newly added root dictionary
    }
    rag_eval_state.set(state)

def get_eval_state() -> dict:
    return rag_eval_state.get()

def append_search_log(search_id: str, raw_ids: list[str], first_rank_ids: list[str]) -> None:
    state = get_eval_state()
    if "retrieval_and_reranking_phase" in state:
        state["retrieval_and_reranking_phase"]["parallel_searches"].append({
            "search_id": search_id,
            "raw_retrieved_chunk_ids": raw_ids,
            "first_reranking_order_ids": first_rank_ids
        })

def register_chunks(docs: list) -> None:
    state = get_eval_state()
    if not state or "chunk_metadata_dictionary" not in state:
        return
        
    for doc in docs:
        doc_id = str(getattr(doc, "id", ""))
        if not doc_id or doc_id in state["chunk_metadata_dictionary"]:
            continue
            
        doc_type = getattr(doc, "type", "unknown")
        meta = doc_meta(doc) or {}
        
        # Extract course code via the metadata dictionary
        if doc_type == "course":
            source_ref = meta.get("course_code", "Unknown Course Code")
            # Courses often store their text payload in the description metadata field
            content = getattr(doc, "content", "") or meta.get("description", "")
        else:
            source_ref = getattr(doc, "url", getattr(doc, "source", "Unknown URL"))
            content = getattr(doc, "content", getattr(doc, "text", ""))
            
        title = getattr(doc, "title", getattr(doc, "name", ""))
        
        state["chunk_metadata_dictionary"][doc_id] = {
            "type": doc_type,
            "source_reference": source_ref,
            "title": title,
            "content": content
        }

def write_eval_log(state: dict = None) -> None:
    if state is None:
        state = get_eval_state()
        
    if not state or not state.get("query_metadata", {}).get("user_query"):
        return
    
    os.makedirs(os.path.dirname(EVAL_FILE_PATH), exist_ok=True)
    with open(EVAL_FILE_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(state) + "\n")