from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    Column,
    ForeignKey,
    Index,
    Integer,
    String,
    TIMESTAMP,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR, UUID
from sqlalchemy.orm import relationship

from .base import Base, EMBEDDING_DIM


class KnowledgeBase(Base):
    __tablename__ = "knowledge_base"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    url = Column(Text, nullable=False)
    title = Column(Text)
    content = Column(Text)
    language = Column(String(10))
    type = Column(String(50))
    category = Column(String(100))
    parent_category = Column(String(100))
    metadata_ = Column("metadata", JSONB, default={})
    embedding = Column(Vector(EMBEDDING_DIM))
    search_vector = Column(TSVECTOR)
    created_at = Column(TIMESTAMP, server_default=func.now())

    versioned_embeddings = relationship("KnowledgeBaseEmbedding", back_populates="kb_entry")


class EmbeddingModel(Base):
    __tablename__ = "embedding_models"

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    version = Column(String(50), nullable=False)
    dimension = Column(Integer, nullable=False)
    description = Column(Text)
    is_active = Column(Boolean, default=False, nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.now())

    embeddings = relationship("KnowledgeBaseEmbedding", back_populates="model")

    __table_args__ = (
        UniqueConstraint("name", "version", name="uq_embedding_model_name_version"),
    )


class KnowledgeBaseEmbedding(Base):
    __tablename__ = "knowledge_base_embeddings"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    kb_id = Column(UUID(as_uuid=True), ForeignKey("knowledge_base.id", ondelete="CASCADE"), nullable=False, index=True)
    model_id = Column(Integer, ForeignKey("embedding_models.id", ondelete="CASCADE"), nullable=False, index=True)
    embedding = Column(Vector(), nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.now())

    kb_entry = relationship("KnowledgeBase", back_populates="versioned_embeddings")
    model = relationship("EmbeddingModel", back_populates="embeddings")

    __table_args__ = (
        UniqueConstraint("kb_id", "model_id", name="uq_kb_model_embedding"),
        Index(
            "idx_kbe_m1_hnsw_cos_expr",
            text("(embedding::vector(384))"),
            postgresql_using="hnsw",
            postgresql_ops={"(embedding::vector(384))": "vector_cosine_ops"},
            postgresql_where=text("model_id = 1"),
        ),
        Index(
            "idx_kbe_m2_hnsw_cos_expr",
            text("(embedding::vector(384))"),
            postgresql_using="hnsw",
            postgresql_ops={"(embedding::vector(384))": "vector_cosine_ops"},
            postgresql_where=text("model_id = 2"),
        ),
        Index(
            "idx_kbe_m3_hnsw_cos_expr",
            text("(embedding::vector(384))"),
            postgresql_using="hnsw",
            postgresql_ops={"(embedding::vector(384))": "vector_cosine_ops"},
            postgresql_where=text("model_id = 3"),
        ),
        Index(
            "idx_kbe_m4_hnsw_cos_expr",
            text("(embedding::vector(384))"),
            postgresql_using="hnsw",
            postgresql_ops={"(embedding::vector(384))": "vector_cosine_ops"},
            postgresql_where=text("model_id = 4"),
        ),
        Index(
            "idx_kbe_m5_hnsw_cos_expr",
            text("(embedding::vector(384))"),
            postgresql_using="hnsw",
            postgresql_ops={"(embedding::vector(384))": "vector_cosine_ops"},
            postgresql_where=text("model_id = 5"),
        ),
    )

