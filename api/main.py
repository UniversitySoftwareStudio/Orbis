from dotenv import load_dotenv

load_dotenv(".env")

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.logging import configure_logging, get_logger
from database.embedding_registry import sync_embedding_models
from database.session import init_db
from routes.auth import router as auth_router
from routes.events import router as events_router
from routes.logout import router as logout_router
from routes.search import router as search_router
from routes.sis import router as sis_router

configure_logging()
logger = get_logger(__name__)

app = FastAPI(
    title="UniChatBot API",
    description="University Chatbot API with JWT authentication and role support",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

init_db()
models = sync_embedding_models()
active = [m for m in models if m.is_active]
if active:
    logger.info("Active embedding model: %s (%s)", active[0].name, active[0].version)
logger.info("API initialized")

app.include_router(auth_router, prefix="/api", tags=["authentication"])
app.include_router(search_router, prefix="/api", tags=["search"])
app.include_router(logout_router, prefix="/api", tags=["logout"])
app.include_router(sis_router, prefix="/api", tags=["sis"])
app.include_router(events_router, prefix="/api", tags=["events"])


@app.get("/")
async def root() -> dict[str, str]:
    return {"message": "API is running"}


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "healthy"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
