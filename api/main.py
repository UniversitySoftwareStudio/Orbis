import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# Import the "Survivor" routers
from routes.auth import router as auth_router
from routes.search import router as search_router
from routes.logout import router as logout_router 

from database.session import init_db

# Load environment variables
load_dotenv(".env")

# Initialize App
app = FastAPI(
    title="UniChatBot API",
    description="University Chatbot API - One Table RAG Architecture",
    version="2.0.0" 
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"], # Your Frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Database
# This will create the 'knowledge_base' table defined in your new models.py
# if it doesn't already exist.
init_db()

# --- Register Routes ---

# 1. Authentication (Login/Register)
app.include_router(auth_router, prefix="/api", tags=["authentication"])

# 2. Chat / Search (The Unified RAG Endpoint)
# This replaces the old 'search' and 'regulations' routers
app.include_router(search_router, prefix="/api", tags=["chat"])

# 3. Logout
app.include_router(logout_router, prefix="/api", tags=["logout"])


# Health Checks
@app.get("/")
async def root():
    return {"message": "UniChatBot RAG API is running"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    # Using "main:app" string helps reload work better in some environments
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)