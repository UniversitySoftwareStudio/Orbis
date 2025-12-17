#!/usr/bin/env python3
"""
Experiment: Embedding Model Benchmark (Auto-Resizing)
"""

import sys
import json
import os
import time
import logging
import re
from pathlib import Path
from typing import List, Dict, Any
from sqlalchemy import text, inspect

# --- Project Imports ---
sys.path.append(str(Path(__file__).parent.parent))

from database.session import SessionLocal
from database.models import DocumentChunk, UniversityDocument, Base
from services.regulation_service import RegulationService
from services import embedding_service

# --- Configuration ---
LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(message)s"
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT, datefmt="%H:%M:%S")
logger = logging.getLogger(__name__)

RESULTS_DIR = Path(__file__).parent / "results" / "chunking_quality"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

DATASETS = [
    RESULTS_DIR / "ground_truths_150w.json"
]

MODELS_TO_TEST = [
    {
        "name": "TEI (All-MiniLM)",
        "slug": "tei_all_minilm",
        "provider": "tei",
        "url": "http://localhost:7860",
        "model_name": None
    },
    {
        "name": "Ollama (Nomic)",
        "slug": "ollama_nomic_embed_text",
        "provider": "ollama",
        "url": "http://localhost:11434",
        "model_name": "nomic-embed-text"
    }
]

class EmbeddingBenchmark:
    def __init__(self):
        self.db = SessionLocal()

    def _reset_embedding_singleton(self, config: Dict[str, Any]):
        """Forces a hard reset of the EmbeddingService configuration."""
        logger.info(f"🔌 Switching configuration to: {config['name']}")
        
        # Patch Module Globals
        embedding_service.EMBEDDING_PROVIDER = config["provider"]
        embedding_service.TEI_URL = config["url"]
        embedding_service.OLLAMA_URL = config["url"]
        embedding_service.OLLAMA_MODEL = config["model_name"]

        # Kill existing instance
        if embedding_service._embedding_service is not None:
            embedding_service._embedding_service = None
        
        # Re-initialize
        try:
            srv = embedding_service.get_embedding_service()
            if config["provider"] == "ollama" and not isinstance(srv.provider, embedding_service.OllamaProvider):
                 raise RuntimeError("Provider mismatch!")
            return srv
        except Exception as e:
            logger.error(f"Failed to connect: {e}")
            raise e

    def _update_table_schema(self, service):
        """
        Drops and Recreates the document_chunks table with the CORRECT vector dimension.
        """
        # 1. Detect Dimension
        test_vec = service.embed_text("test")
        dim = len(test_vec)
        logger.info(f"📏 Model Dimension: {dim}")
        
        # 2. Raw SQL to Drop & Recreate
        # We use raw SQL because altering SQLAlchemy models at runtime is tricky
        try:
            self.db.execute(text("DROP TABLE IF EXISTS document_chunks CASCADE;"))
            self.db.commit()
            
            # Recreate with new dimension
            create_sql = f"""
            CREATE TABLE document_chunks (
                id SERIAL PRIMARY KEY,
                document_id INTEGER REFERENCES university_documents(id),
                chunk_index INTEGER NOT NULL,
                content TEXT NOT NULL,
                embedding vector({dim})
            );
            """
            self.db.execute(text(create_sql))
            self.db.commit()
            logger.info(f"✅ Recreated table 'document_chunks' with vector({dim})")
            
        except Exception as e:
            self.db.rollback()
            logger.critical(f"Failed to update schema: {e}")
            raise e

    def _prepare_parent_doc(self):
        """Ensures the parent document exists."""
        # Check if table exists (it might have been dropped if we cleared everything)
        # But we only dropped document_chunks. university_documents should exist.
        doc = self.db.query(UniversityDocument).filter_by(source_url="bench_dummy").first()
        if not doc:
            doc = UniversityDocument(
                source_url="bench_dummy", 
                title="Benchmark GT", 
                raw_content="...",
                summary="Bench", 
                keywords="bench"
            )
            self.db.add(doc)
            self.db.commit()
        return doc.id

    def _index_chunks(self, chunks: List[str], doc_id: int, service):
        """Embeds and inserts text chunks."""
        total = len(chunks)
        logger.info(f"📥 Indexing {total} chunks...")
        start_time = time.time()
        
        content_id_map = {}
        
        # We must use RAW SQL insert because the SQLAlchemy model 'DocumentChunk' 
        # is still bound to the old dimension (384) in Python memory.
        insert_sql = text("""
            INSERT INTO document_chunks (document_id, chunk_index, content, embedding)
            VALUES (:doc_id, :idx, :content, :emb)
            RETURNING id
        """)

        for i, content in enumerate(chunks):
            try:
                vector = service.embed_text(content)
                
                # Execute Raw Insert
                result = self.db.execute(insert_sql, {
                    "doc_id": doc_id,
                    "idx": i,
                    "content": content,
                    "emb": str(vector) # pgvector expects string or list
                })
                new_id = result.scalar()
                content_id_map[content] = new_id

                if (i + 1) % 20 == 0:
                    self.db.commit()
                    print(f"\r   ... Indexed {i+1}/{total}", end="", flush=True)

            except Exception as e:
                self.db.rollback()
                logger.warning(f"Failed chunk {i}: {e}")

        self.db.commit()
        print("") # Newline
        
        duration = time.time() - start_time
        logger.info(f"✅ Indexing complete in {duration:.2f}s")
        return content_id_map

    def _check_keyword_match(self, retrieved_text: str, keywords: List[str]) -> tuple[List[str], bool]:
        if not keywords: return [], False
        found = [kw for kw in keywords if kw.lower() in retrieved_text.lower()]
        is_match = len(found) >= (len(keywords) / 2)
        return found, is_match

    def _run_benchmark(self, dataset_path: Path, ground_truths: List[Dict], config: Dict, service):
            
            # 1. Update DB Schema & Index
            self._update_table_schema(service)
            doc_id = self._prepare_parent_doc()
            
            unique_contents = list({item["chunk_content"] for item in ground_truths})
            content_id_map = self._index_chunks(unique_contents, doc_id, service)

            # 2. Retrieval
            logger.info("🔎 Starting Retrieval Benchmark (Raw SQL Mode)...")
            
            # We perform Raw SQL Search to bypass SQLAlchemy's class-level dimension check
            # This allows searching 768-dim vectors even if models.py says 384
            search_sql = text("""
                SELECT content 
                FROM document_chunks 
                ORDER BY embedding <=> :query_embedding 
                LIMIT 3
            """)
            
            detailed_results = []
            correct_count = 0
            keyword_match_count = 0
            reciprocal_ranks = []
            
            valid_queries = [gt for gt in ground_truths if gt.get("chunk_content") in content_id_map]
            total_questions = len(valid_queries)

            for i, item in enumerate(valid_queries):
                question = item["question"]
                target_content = item["chunk_content"]
                target_id = content_id_map[target_content]
                keywords = item.get("keywords", [])
                
                try:
                    # Embed Question
                    q_vector = service.embed_text(question)

                    # Execute Raw Search
                    # We cast to string because pgvector driver handles string->vector conversion 
                    # safer than object mapping when dimensions mismatch
                    results = self.db.execute(search_sql, {"query_embedding": str(q_vector)}).fetchall()
                    
                    # Results are tuples: (content,)
                    retrieved_contents = [row[0] for row in results]
                    
                    # Map back to IDs
                    retrieved_ids = []
                    for content in retrieved_contents:
                        if content in content_id_map:
                            retrieved_ids.append(content_id_map[content])

                    # --- Metrics Logic ---
                    is_found = target_id in retrieved_ids
                    
                    rank = None
                    if is_found:
                        rank = retrieved_ids.index(target_id) + 1
                        reciprocal_ranks.append(1.0 / rank)
                        correct_count += 1
                    else:
                        reciprocal_ranks.append(0.0)

                    top_text = retrieved_contents[0] if retrieved_contents else ""
                    kw_found, kw_match = self._check_keyword_match(top_text, keywords)
                    if kw_match: keyword_match_count += 1

                    detailed_results.append({
                        "question": question,
                        "expected_chunk_id": target_id,
                        "retrieved_chunk_ids": retrieved_ids,
                        "found": is_found,
                        "rank": rank,
                        "keywords": keywords,
                        "keywords_found": kw_found,
                        "keyword_match": kw_match
                    })

                    if (i + 1) % 25 == 0:
                        print(f"\r   ... Query {i+1}/{total_questions}", end="", flush=True)

                except Exception as e:
                    logger.error(f"Error on query: {e}")

            print("")
            
            # Stats Calculation
            accuracy = correct_count / total_questions if total_questions else 0
            mrr = sum(reciprocal_ranks) / len(reciprocal_ranks) if reciprocal_ranks else 0
            kw_accuracy = keyword_match_count / total_questions if total_questions else 0

            chunk_size_match = re.search(r'(\d+)w', dataset_path.name)
            chunk_size = int(chunk_size_match.group(1)) if chunk_size_match else 0

            return {
                "model_name": config["name"],
                "dataset": dataset_path.name,
                "chunk_size": chunk_size,
                "total_questions": total_questions,
                "correct_retrievals": correct_count,
                "accuracy": accuracy,
                "mrr": mrr,
                "keyword_matches": keyword_match_count,
                "keyword_accuracy": kw_accuracy,
                "results": detailed_results
            }

    def run(self):
        logger.info("="*50)
        logger.info("🚀 STARTING BENCHMARK (Auto-Schema Mode)")
        logger.info("="*50)

        for dataset_path in DATASETS:
            if not dataset_path.exists():
                logger.error(f"Missing dataset: {dataset_path}")
                continue

            with open(dataset_path, "r", encoding="utf-8") as f:
                ground_truths = json.load(f)

            for config in MODELS_TO_TEST:
                logger.info(f"\n👉 DATASET: {dataset_path.name} | MODEL: {config['name']}")
                
                try:
                    svc = self._reset_embedding_singleton(config)
                    report = self._run_benchmark(dataset_path, ground_truths, config, svc)
                    
                    filename = f"results_{config['slug']}_{dataset_path.name}"
                    save_path = RESULTS_DIR / filename
                    
                    with open(save_path, "w", encoding="utf-8") as f:
                        json.dump(report, f, indent=2)
                    
                    logger.info(f"💾 Saved report: {save_path.name}")
                    logger.info(f"🏆 Score: {report['accuracy']*100:.2f}% (MRR: {report['mrr']:.3f})")

                except Exception as e:
                    logger.critical(f"❌ Failed cycle: {e}", exc_info=True)


if __name__ == "__main__":
    try:
        bench = EmbeddingBenchmark()
        bench.run()
    except KeyboardInterrupt:
        logger.warning("⚠️ Benchmark interrupted.")