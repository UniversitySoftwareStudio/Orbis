from sqlalchemy import distinct, func, select

from database.models import EmbeddingModel, KnowledgeBase, KnowledgeBaseEmbedding
from database.session import SessionLocal


def main() -> int:
    db = SessionLocal()
    try:
        active_model = db.scalars(
            select(EmbeddingModel).where(EmbeddingModel.is_active.is_(True)).limit(1)
        ).first()
        if active_model is None:
            print(
                "[EMBEDDING_VERIFICATION_FAILED] "
                "No active embedding model found (embedding_models.is_active=true). "
                "Startup aborted."
            )
            return 1

        kb_count = db.scalar(select(func.count()).select_from(KnowledgeBase)) or 0
        emb_count = (
            db.scalar(
                select(func.count(distinct(KnowledgeBaseEmbedding.kb_id))).where(
                    KnowledgeBaseEmbedding.model_id == active_model.id
                )
            )
            or 0
        )

        if kb_count != emb_count:
            missing = kb_count - emb_count
            print(
                "[EMBEDDING_VERIFICATION_FAILED] "
                f"active_model={active_model.name} "
                f"kb_count={kb_count} embedding_count={emb_count} missing={missing}. "
                "knowledge_base_embeddings must match knowledge_base 1:1 for the active model. "
                "Startup aborted."
            )
            return 1

        print(
            "[EMBEDDING_VERIFICATION_OK] "
            f"active_model={active_model.name} kb_count={kb_count} embedding_count={emb_count}"
        )
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())

