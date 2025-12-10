"""
Base class for all RAG experiments.
Provides minimal utilities - experiments handle their own logic.
"""

import json
import random
from pathlib import Path
from typing import List, Dict
from abc import ABC, abstractmethod
from sqlalchemy.orm import Session
from database.models import UniversityDocument, DocumentChunk
from services.llm_service import LLMService


class BaseExperiment(ABC):
    """Base class for RAG system experiments. Only provides utility methods."""
    
    def __init__(self, db: Session, experiment_name: str):
        self.db = db
        self.experiment_name = experiment_name
        self.llm_service = LLMService()
        self.output_dir = Path(__file__).parent / "results" / experiment_name
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def delete_all_chunks(self):
        """Delete all existing chunks from the database."""
        count = self.db.query(DocumentChunk).count()
        self.db.query(DocumentChunk).delete()
        self.db.commit()
        print(f"Deleted {count} existing chunks")
        
    def chunk_all_documents(self, chunk_size: int, overlap: int) -> int:
        """Chunk all documents with given strategy."""
        from services.regulation_service import RegulationService
        
        service = RegulationService(self.db)
        docs = self.db.query(UniversityDocument).all()
        
        total_chunks = 0
        for doc in docs:
            count = service.chunk_document(doc.id, chunk_size=chunk_size, overlap=overlap)
            total_chunks += count
            
        print(f"Created {total_chunks} chunks (size={chunk_size}, overlap={overlap})")
        return total_chunks
        
    def sample_chunks(self, n: int = 10) -> List[DocumentChunk]:
        """Randomly sample N chunks from the database."""
        all_chunks = self.db.query(DocumentChunk).all()
        return random.sample(all_chunks, min(n, len(all_chunks)))
        
    def save_json(self, data: Dict, filename: str):
        """Save data to JSON file."""
        filepath = self.output_dir / filename
        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)
        print(f"Saved to {filepath}")
        
    def load_json(self, filename: str) -> Dict:
        """Load data from JSON file."""
        filepath = self.output_dir / filename
        if not filepath.exists():
            raise FileNotFoundError(f"File not found: {filepath}")
        with open(filepath, "r") as f:
            return json.load(f)
        
    @abstractmethod
    def run(self):
        """Run the experiment. Must be implemented by subclasses."""
        pass
