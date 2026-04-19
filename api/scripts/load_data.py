import sys
import os
import json
import psycopg2
from psycopg2.extras import Json
from dotenv import load_dotenv
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeRemainingColumn, MofNCompleteColumn

# Path setup to find your data
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
sys.path.append(BASE_DIR)

load_dotenv()

# Config
DB_PARAMS = {
    "dbname": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "host": os.getenv("DB_HOST"),
    "port": os.getenv("DB_PORT")
}

FILES = [
    #"bilgi_courses_data.jsonl", 
    #"bilgi_university_data.jsonl",
    "bilgi_pdfs_important.jsonl"
    #bilgi_pdfs_irrelevant.jsonl and bilgi pdfs_resumers.jsonl contain data that we don't want to include in the db. So we don't include them here.
]

CHUNK_SIZE = 150
CHUNK_OVERLAP = 30

def get_db_connection():
    try:
        conn = psycopg2.connect(**DB_PARAMS)
        return conn
    except Exception as e:
        print(f"Database connection failed: {e}")
        sys.exit(1)

def simple_chunker(text, chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
    if not text: return []
    words = text.split()
    if len(words) <= chunk_size: return [text]
    
    chunks = []
    for i in range(0, len(words), chunk_size - overlap):
        chunk_words = words[i : i + chunk_size]
        chunks.append(" ".join(chunk_words))
        if i + chunk_size >= len(words): break
    return chunks

def setup_database(conn):
    print("🔨 Setting up Database Schema...")
    with conn.cursor() as cur:
        cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        
        # Create Table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS knowledge_base (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                url TEXT NOT NULL,
                title TEXT,
                content TEXT,
                language VARCHAR(10),
                type VARCHAR(50),
                metadata JSONB DEFAULT '{}'::jsonb,
                embedding vector(384),
                created_at TIMESTAMP DEFAULT NOW()
            );
        """)

        # Hybrid Search (Dynamic Language Support)
        cur.execute("ALTER TABLE knowledge_base DROP COLUMN IF EXISTS search_vector;")
        cur.execute("""
            ALTER TABLE knowledge_base 
            ADD COLUMN search_vector tsvector 
            GENERATED ALWAYS AS (
                setweight(to_tsvector(
                    CASE WHEN language = 'tr' THEN 'turkish'::regconfig ELSE 'english'::regconfig END, 
                    coalesce(title, '')
                ), 'A') || 
                setweight(to_tsvector(
                    CASE WHEN language = 'tr' THEN 'turkish'::regconfig ELSE 'english'::regconfig END, 
                    coalesce(content, '')
                ), 'B')
            ) STORED;
        """)

        # Indexes
        cur.execute("CREATE INDEX IF NOT EXISTS idx_search_vector ON knowledge_base USING GIN(search_vector);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_kb_type ON knowledge_base(type);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_kb_url ON knowledge_base(url);")
        
        conn.commit()
    print("✅ Schema Ready.")

def clean_text(text):
    """Removes NUL (0x00) characters which crash PostgreSQL."""
    if not text:
        return text
    return text.replace('\x00', '')

def process_file(conn, filename):
    filepath = os.path.join(DATA_DIR, filename)
    if not os.path.exists(filepath):
        print(f"⚠️  File not found: {filepath}")
        return

    # 1. Pre-scan to get total line count (Active Progress Requirement)
    print(f"📊 Counting records in {filename}...")
    with open(filepath, 'r', encoding='utf-8') as f:
        total_lines = sum(1 for _ in f)

    cursor = conn.cursor()
    batch_data = []
    
    insert_query = """
        INSERT INTO knowledge_base (url, title, content, language, type, metadata)
        VALUES (%s, %s, %s, %s, %s, %s)
    """

    # 2. Rich Progress Bar Context
    with Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        BarColumn(bar_width=40, style="cyan", complete_style="blue"),
        MofNCompleteColumn(),      # Shows: "150/1200"
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeRemainingColumn(),     # Shows: "00:45 left"
    ) as progress:
        
        task = progress.add_task(f"Processing {filename}...", total=total_lines)
        
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    row = json.loads(line)
                    
                    # --- COURSE LOGIC ---
                    if row.get('type') == 'course':
                        batch_data.append((
                            row['url'],
                            row['title'], 
                            row['content'],
                            row['language'],
                            'course',
                            Json(row['metadata'])
                        ))

                    # --- WEB PAGE & PDF LOGIC ---
                    else:
                        chunks = simple_chunker(row['content'])
                        doc_type = row.get('type', 'web_page')
                        
                        for i, chunk_text in enumerate(chunks):
                            meta = row['metadata'].copy()
                            meta['chunk_index'] = i
                            meta['total_chunks'] = len(chunks)
                            
                            # Handle Dates (Web vs PDF)
                            if row.get('detected_date'): 
                                meta['date'] = row['detected_date']
                            elif meta.get('final_date'): 
                                meta['date'] = meta['final_date']

                            # Handle other meta
                            if row.get('mentioned_years'): 
                                meta['years'] = row['mentioned_years']
                            if row.get('metadata', {}).get('breadcrumbs'): 
                                meta['breadcrumbs'] = row['metadata']['breadcrumbs']

                            batch_data.append((
                                row['url'],
                                row['title'],
                                chunk_text,
                                row.get('language', 'en'),
                                doc_type,
                                Json(meta)
                            ))

                    # Batch Insert
                    if len(batch_data) >= 100:
                        cursor.executemany(insert_query, batch_data)
                        conn.commit()
                        batch_data = []
                    
                    # Update Progress Bar
                    progress.update(task, advance=1)

                except json.JSONDecodeError: 
                    continue
                except Exception as e: 
                    # Optional: Print error without breaking the bar
                    # progress.console.print(f"[red]Error:[/red] {e}")
                    continue

    # Flush remaining batch
    if batch_data:
        cursor.executemany(insert_query, batch_data)
        conn.commit()
    
    print(f"✅ Loaded {filename} successfully.")

if __name__ == "__main__":
    conn = get_db_connection()
    setup_database(conn)
    
    for f in FILES:
        process_file(conn, f)
        
    conn.close()
    print("🎉 Ingestion Complete.")