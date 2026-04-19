from pathlib import Path
from shlex import split as shell_split
from typing import Any

import yaml
from sqlalchemy import select

from database.models import EMBEDDING_DIM, EmbeddingModel
from database.session import SessionLocal
from embedding.config import EMBEDDING_MODEL


def _compose_path() -> Path:
    return Path(__file__).resolve().parents[2] / "docker-compose.yml"


def _extract_model_id(command_value: Any) -> str | None:
    if not command_value:
        return None
    if isinstance(command_value, str):
        parts = shell_split(command_value)
    elif isinstance(command_value, list):
        parts = [str(x) for x in command_value]
    else:
        return None

    for i, token in enumerate(parts):
        if token == "--model-id" and i + 1 < len(parts):
            return parts[i + 1]
        if token.startswith("--model-id="):
            return token.split("=", 1)[1]
    return None


def discover_embedding_models_from_compose() -> list[str]:
    path = _compose_path()
    if not path.exists():
        return []

    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    services = (data.get("services") or {})

    found: list[str] = []
    for service_name, service in services.items():
        if not isinstance(service_name, str) or not service_name.startswith("embedding-"):
            continue
        if service_name == "embedding-lb":
            continue
        model_id = _extract_model_id((service or {}).get("command"))
        if model_id and model_id not in found:
            found.append(model_id)
    return found


def sync_embedding_models() -> list[EmbeddingModel]:
    """Upsert compose-discovered models and activate EMBEDDING_MODEL only."""
    db = SessionLocal()
    try:
        discovered = discover_embedding_models_from_compose()
        known_models = discovered or [EMBEDDING_MODEL]

        by_name: dict[str, EmbeddingModel] = {
            row.name: row
            for row in db.scalars(select(EmbeddingModel)).all()
        }

        for name in known_models:
            if name not in by_name:
                row = EmbeddingModel(
                    name=name,
                    version="v1",
                    dimension=EMBEDDING_DIM,
                    description="Auto-registered from docker-compose model list",
                    is_active=False,
                )
                db.add(row)
                by_name[name] = row
            else:
                if by_name[name].dimension is None:
                    by_name[name].dimension = EMBEDDING_DIM

        for row in by_name.values():
            row.is_active = row.name == EMBEDDING_MODEL

        # If configured model is not discovered, still register + activate it.
        if EMBEDDING_MODEL not in by_name:
            row = EmbeddingModel(
                name=EMBEDDING_MODEL,
                version="v1",
                dimension=EMBEDDING_DIM,
                description="Auto-registered from EMBEDDING_MODEL",
                is_active=True,
            )
            db.add(row)

        db.commit()
        return list(db.scalars(select(EmbeddingModel).order_by(EmbeddingModel.id.asc())).all())
    finally:
        db.close()
