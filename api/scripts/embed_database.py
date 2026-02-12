import sys
import os
import psycopg2
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeRemainingColumn, MofNCompleteColumn
from rich.console import Console

# Path setup
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
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

BATCH_SIZE = 50
console = Console()

def get_db_connection():
    try:
        return psycopg2.connect(**DB_PARAMS)
    except Exception as e:
        console.print(f"[bold red]❌ Database Connection Failed:[/bold red] {e}")
        sys.exit(1)

def generate_embeddings():
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # 1. Check how many need processing
        console.print("[cyan]📊 Counting pending embeddings...[/cyan]")
        cursor.execute("SELECT COUNT(*) FROM knowledge_base WHERE embedding IS NULL")
        total_pending = cursor.fetchone()[0]
        
        if total_pending == 0:
            console.print("[bold green]✅ No pending embeddings found. Database is up to date![/bold green]")
            return

        console.print(f"[bold green]🚀 Found {total_pending} chunks to embed.[/bold green]")
        console.print("[dim]   (You can press CTRL+C at any time to pause safely)[/dim]")

        # 2. Load Model
        console.print("[yellow]⏳ Loading Embedding Model (this takes a few seconds)...[/yellow]")
        model = SentenceTransformer('sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2')
        console.print("[green]✅ Model ready.[/green]")

        # 3. Process with Progress Bar
        with Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            BarColumn(bar_width=40, style="cyan", complete_style="blue"),
            MofNCompleteColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeRemainingColumn(),
            console=console
        ) as progress:
            
            task = progress.add_task("Generating Vectors...", total=total_pending)
            
            while True:
                # Fetch Batch
                cursor.execute("""
                    SELECT id, title, content 
                    FROM knowledge_base 
                    WHERE embedding IS NULL 
                    LIMIT %s
                """, (BATCH_SIZE,))
                
                rows = cursor.fetchall()
                if not rows:
                    break

                # Prepare Batch Text
                texts_to_embed = []
                ids_to_update = []
                
                for r in rows:
                    row_id, title, content = r
                    safe_title = title if title else ""
                    # Combine Title + Content for context-aware embedding
                    text = f"{safe_title}\n\n{content}"
                    texts_to_embed.append(text)
                    ids_to_update.append(row_id)

                # Generate Vectors
                embeddings = model.encode(texts_to_embed)

                # Update DB
                update_data = []
                for i, emb in enumerate(embeddings):
                    update_data.append((emb.tolist(), ids_to_update[i]))

                cursor.executemany(
                    "UPDATE knowledge_base SET embedding = %s::vector WHERE id = %s",
                    update_data
                )
                conn.commit() # Save progress after every batch

                # Advance Progress
                progress.update(task, advance=len(rows))

        console.print("\n[bold green]🎉 All embeddings generated successfully![/bold green]")

    except KeyboardInterrupt:
        conn.rollback() # Discard any half-finished batch
        console.print("\n\n[bold red]🛑 Process paused by user (CTRL+C).[/bold red]")
        console.print("[yellow]   ✅ All progress up to the last batch was saved.[/yellow]")
        console.print("[yellow]   ▶️  Run the script again to resume from where you left off.[/yellow]")
        
    except Exception as e:
        console.print(f"\n[bold red]❌ Unexpected Error:[/bold red] {e}")
        
    finally:
        if conn:
            conn.close()
            console.print("[dim]🔌 Database connection closed.[/dim]")

if __name__ == "__main__":
    generate_embeddings()