import sys
import os
import time
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv

# Ensure we can find the api module if running from scripts/
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load env vars (DB credentials)
load_dotenv() 

# --- CONFIG ---
# Construct DB URL from your .env
DATABASE_URL = f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
BATCH_SIZE = 50
# This is the exact model matching your DB dimension (384)
MODEL_NAME = 'sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2'

def get_db_session():
    try:
        engine = create_engine(DATABASE_URL)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        return SessionLocal()
    except Exception as e:
        print(f"❌ Database Connection Failed: {e}")
        sys.exit(1)

def embed_data():
    print(f"🚀 Starting Embedder using model: {MODEL_NAME}")
    
    # Check for GPU (CUDA) or MPS (Mac) or CPU
    device = "cpu"
    if os.environ.get("CUDA_VISIBLE_DEVICES"):
        device = "cuda"
    print(f"⚙️  Running on: {device.upper()}")
    
    try:
        model = SentenceTransformer(MODEL_NAME, device=device)
    except Exception as e:
        print(f"❌ Error loading model: {e}")
        return

    db = get_db_session()
    
    while True:
        try:
            # 1. Fetch rows with NULL embeddings
            # We use raw SQL for speed and simplicity in batch updates
            query = text("""
                SELECT id, title, content, type, metadata, language
                FROM knowledge_base 
                WHERE embedding IS NULL 
                LIMIT :limit
            """)
            result = db.execute(query, {"limit": BATCH_SIZE}).fetchall()
            
            if not result:
                print("✅ All rows embedded. Exiting.")
                break

            # 2. Prepare Batch
            texts = []
            ids = []
            
            for row in result:
                # Unpack row (order matters based on SELECT)
                r_id, r_title, r_content, r_type, r_meta, r_lang = row
                
                # Smart Context Formatting
                if r_type == 'course':
                    dept = r_meta.get('department', '') if r_meta else ''
                    # Format: "Course: CMPE 101. Dept: Engineering. Content: ..."
                    text_input = f"Course: {r_title}. Department: {dept}. Description: {r_content}"
                else:
                    # Format: "Title. Content"
                    text_input = f"{r_title}. {r_content}"
                
                texts.append(text_input)
                ids.append(r_id)

            # 3. Generate Embeddings
            print(f"   Processing batch of {len(texts)}...")
            embeddings = model.encode(texts)

            # 4. Update Database
            for i, emb in enumerate(embeddings):
                update_stmt = text("UPDATE knowledge_base SET embedding = :emb WHERE id = :oid")
                db.execute(update_stmt, {"emb": emb.tolist(), "oid": ids[i]})
            
            db.commit()
            print(f"   -> Saved {len(texts)} vectors.")
            
        except Exception as e:
            print(f"❌ Error in batch: {e}")
            db.rollback()
            time.sleep(5) # Wait before retrying

    db.close()

if __name__ == "__main__":
    embed_data()