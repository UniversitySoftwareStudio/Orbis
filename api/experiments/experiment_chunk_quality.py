#!/usr/bin/env python3
"""
Experiment 1: Chunking Quality Check

Tests if we can find the right regulation rules with different chunk sizes.
"""

import sys
import json as json_lib
import os
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.append(str(Path(__file__).parent.parent))

from database.session import SessionLocal
from database.models import DocumentChunk
from experiments.base_experiment import BaseExperiment
from services.regulation_service import RegulationService


class ChunkingQualityExperiment(BaseExperiment):
    """
    Tests retrieval quality across different chunking strategies.
    """

    def __init__(self):
        db = SessionLocal()
        super().__init__(db, experiment_name="chunking_quality")
        self.chunk_sizes = [100, 150]
        self.overlap_ratio = 0.1
        self.ground_truth_samples = 1000
        self.max_workers = 10  # Parallel threads

    def run(self):
        """Run the complete experiment."""
        print("=" * 60)
        print("🧪 Experiment 1: Chunking Quality Check")
        print("=" * 60)

        for chunk_size in self.chunk_sizes:
            print(f"\n{'=' * 60}")
            print(f"Testing Chunk Size: {chunk_size} words")
            print(f"{'=' * 60}\n")

            overlap = int(chunk_size * self.overlap_ratio)
            gt_filename = f"ground_truths_{chunk_size}w.json"
            
            # We assume the BaseExperiment saves results in a specific folder. 
            # We construct the path to check for existence.
            # Adjust 'results/chunking_quality' if your BaseExperiment uses a different path structure.
            gt_file_path = Path(__file__).parent / "results" / "chunking_quality" / gt_filename

            # Step 1: Delete all existing chunks (Always required to reset DB state)
            self.delete_all_chunks()

            # Step 2: Re-chunk with current strategy (Always required to fill DB)
            total_chunks = self.chunk_all_documents(chunk_size, overlap)

            ground_truths = []

            # CHECK: Do we already have ground truths?
            if gt_file_path.exists():
                print(f"📂 Found existing ground truths at: {gt_filename}")
                print("🔄 Loading and re-mapping IDs to new database chunks...")
                ground_truths = self._load_and_remap_ground_truths(gt_file_path)
            else:
                # Step 3: Sample random chunks
                sampled_chunks = self.sample_chunks(n=self.ground_truth_samples)
                print(f"📋 Sampled {len(sampled_chunks)} chunks for ground truth generation")

                # Step 4: Generate ground truths using AI (parallel)
                ground_truths = self._generate_ground_truths(sampled_chunks)
                print(f"✅ Generated {len(ground_truths)} ground truth Q&A pairs")

                # Step 5: Save ground truths
                self.save_json(ground_truths, gt_filename)

            if not ground_truths:
                print("⚠️ No ground truths available. Skipping test.")
                continue

            # Step 6: Test retrieval quality
            report = self._test_retrieval_quality(ground_truths, chunk_size)

            # Step 7: Save report
            self.save_json(report, f"report_{chunk_size}w.json")

        print("\n" + "=" * 60)
        print("Experiment Complete!")
        print("=" * 60)

    def _load_and_remap_ground_truths(self, filepath):
        """
        Loads existing ground truths and updates their chunk_ids.
        Since we re-chunked the database, the old IDs in the JSON file are invalid.
        We must find the new chunk ID by matching the content.
        """
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json_lib.load(f)
        except Exception as e:
            print(f"❌ Error loading JSON: {e}")
            return []

        remapped_data = []
        not_found_count = 0

        for item in data:
            content_to_match = item["chunk_content"]
            
            # Find the chunk in the NEW database that matches the OLD content
            # We filter by exact content match
            chunk = self.db.query(DocumentChunk).filter_by(content=content_to_match).first()
            
            if chunk:
                # Update the ID to the new database ID
                item["chunk_id"] = chunk.id
                remapped_data.append(item)
            else:
                not_found_count += 1
        
        print(f"   ✅ Successfully remapped {len(remapped_data)} items.")
        if not_found_count > 0:
            print(f"   ⚠️ Warning: Could not find {not_found_count} chunks in new DB (content mismatch).")

        return remapped_data

    def _generate_single_ground_truth(self, chunk):
        """Generate a single ground truth Q&A pair."""
        prompt = f"""Based on this text chunk from a university regulation document:

"{chunk.content}"

Generate a specific question that can ONLY be answered using information in this exact chunk.
Also extract 2-3 critical keywords from the chunk that MUST appear in a correct answer.

Return ONLY a JSON object with this format:
{{"question": "your question here", "expected_answer": "the answer from the chunk", "keywords": ["keyword1", "keyword2", "keyword3"]}}"""

        try:
            response = ""
            for token in self.llm_service.generate(prompt):
                response += token

            qa_pair = json_lib.loads(response.strip())

            return {
                "chunk_id": chunk.id,
                "chunk_content": chunk.content,
                "document_title": chunk.document.title,
                "question": qa_pair["question"],
                "expected_answer": qa_pair["expected_answer"],
                "keywords": qa_pair["keywords"],
            }
        except Exception:
            return None

    def _generate_ground_truths(self, chunks):
        """Generate ground truth Q&A pairs using AI with keywords (parallel)."""
        ground_truths = []
        failed = 0
        total = len(chunks)

        print(f"🚀 Generating ground truths with {self.max_workers} parallel workers...")

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {
                executor.submit(self._generate_single_ground_truth, chunk): i 
                for i, chunk in enumerate(chunks)
            }

            for future in as_completed(futures):
                result = future.result()
                if result:
                    ground_truths.append(result)
                else:
                    failed += 1

                done = len(ground_truths) + failed
                if done % 50 == 0 or done == total:
                    print(f"   Progress: {done}/{total} | ✅ {len(ground_truths)} | ❌ {failed}")

        print(f"   Completed: ✅ {len(ground_truths)} | ❌ {failed}")
        return ground_truths

    def _test_retrieval_quality(self, ground_truths, chunk_size):
        """
        Test if we can retrieve the correct chunks for each question.
        Uses keyword matching to verify the retrieved chunk contains critical information.
        """
        service = RegulationService(self.db)
        results = []
        correct_count = 0
        keyword_match_count = 0
        reciprocal_ranks = []

        print(f"\n🔍 Testing retrieval for {len(ground_truths)} questions...")

        for i, gt in enumerate(ground_truths):
            question = gt["question"]
            expected_chunk_id = gt["chunk_id"]
            keywords = gt.get("keywords", [])

            # Retrieve top 3 chunks
            retrieved = service.search_regulations(question, limit=3)

            # Check if the correct chunk is in top 3
            retrieved_chunk_data = []
            for r in retrieved:
                chunk = (
                    self.db.query(DocumentChunk).filter_by(content=r["content"]).first()
                )
                if chunk:
                    retrieved_chunk_data.append(chunk)

            retrieved_ids = [c.id for c in retrieved_chunk_data]
            found = expected_chunk_id in retrieved_ids

            # Calculate reciprocal rank
            if expected_chunk_id in retrieved_ids:
                rank = retrieved_ids.index(expected_chunk_id) + 1
                reciprocal_ranks.append(1 / rank)
            else:
                reciprocal_ranks.append(0)

            # Check if top retrieved chunk contains keywords
            keywords_found = []
            if retrieved_chunk_data and keywords:
                top_chunk = retrieved_chunk_data[0].content.lower()
                keywords_found = [kw for kw in keywords if kw.lower() in top_chunk]

            keyword_match = (
                len(keywords_found) >= len(keywords) * 0.5 if keywords else False
            )

            if found:
                correct_count += 1
            if keyword_match:
                keyword_match_count += 1

            results.append(
                {
                    "question": question,
                    "expected_chunk_id": expected_chunk_id,
                    "retrieved_chunk_ids": retrieved_ids,
                    "found": found,
                    "rank": retrieved_ids.index(expected_chunk_id) + 1 if found else None,
                    "keywords": keywords,
                    "keywords_found": keywords_found,
                    "keyword_match": keyword_match,
                }
            )

            status = "✅" if found else "❌"
            kw_status = f"{len(keywords_found)}/{len(keywords)}" if keywords else ""
            if (i + 1) % 10 == 0:  # Print every 10th to reduce spam, or keep as is
                 print(f"   [{i+1}/{len(ground_truths)}] {status} Found: {found} {kw_status}")

        accuracy = correct_count / len(ground_truths) if ground_truths else 0
        keyword_accuracy = (
            keyword_match_count / len(ground_truths) if ground_truths else 0
        )
        mrr = sum(reciprocal_ranks) / len(reciprocal_ranks) if reciprocal_ranks else 0

        report = {
            "chunk_size": chunk_size,
            "total_questions": len(ground_truths),
            "correct_retrievals": correct_count,
            "accuracy": accuracy,
            "mrr": mrr,
            "keyword_matches": keyword_match_count,
            "keyword_accuracy": keyword_accuracy,
            "results": results,
        }

        print(f"\nRecall@3: {accuracy * 100:.1f}% ({correct_count}/{len(ground_truths)})")
        print(f"MRR: {mrr:.3f}")
        print(f"Keyword Accuracy: {keyword_accuracy * 100:.1f}% ({keyword_match_count}/{len(ground_truths)})")

        return report


if __name__ == "__main__":
    experiment = ChunkingQualityExperiment()
    experiment.run()