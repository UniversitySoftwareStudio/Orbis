import os

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", "384"))

