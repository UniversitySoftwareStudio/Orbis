# 🧠 Orbis API (RAG Backend)

This is the backend for the Orbis RAG system. It uses a **Hybrid Search Architecture** that combines the precision of SQL with the semantic understanding of Vector Search, orchestrated by an intelligent Router.

## 🚀 Main Capabilities

* **Hybrid Search:** Automatically switches between:
    * **SQL Tool:** For precise lookups ("What is CMPE 101?"), lists ("List computer courses"), and direct comparisons.
    * **Vector Tool:** For fuzzy questions ("How do I apply for a minor?"), conceptual queries, and general knowledge.
* **Multi-Lingual:** Native support for both **Turkish** and **English** queries without translation loss.
* **Batch & Compare:** Can fetch multiple specific entities in a single database round-trip for accurate comparisons.
* **Metadata Aware:** Injects rich metadata (ECTS, Credits, Schedule) into the context, allowing the LLM to answer detailed attribute questions.
* **Smart Context Expansion**
    * **The Problem:** Vector search often finds "Fragment B" (e.g., Step 3) but misses "Fragment A" (Step 1).
    * **The Solution:** If a Web Page is found, the system automatically fetches **the entire document** (all chunks) to guarantee complete context.
* **Neural Reranking (Jina AI)**
    * **The Problem:** Expanding documents creates too much noise (80+ chunks).
    * **The Solution:** We use **Jina Reranker v2 (Multilingual)** to score and sort these chunks.
    * **Result:** The LLM receives only the **Top 5** most relevant chunks, ensuring high accuracy and low latency (< 2s).

## 🛠️ Architecture

### The "One-Table" Approach
Instead of scattering data across `courses`, `people`, and `pages` tables, we use a single unified table:

| Column | Type | Description |
| :--- | :--- | :--- |
| `id` | UUID | Unique identifier |
| `url` | String | Origin link of the source |
| `title` | String | Course name or Page title |
| `content` | Text | The actual text chunk |
| `language` | String | Language code of the source (`en` or `tr`) |
| `type` | String | `course` or `web_page` |
| **`metadata`** | JSONB | Flexible attributes (ECTS, Year, Code, etc.) |
| **`embedding`** | Vector | 384-dim vector (MiniLM-L12) |
| `created_at` | Timestamp | Date at which the source is added to the database |
| **`search_vector`** | tsvector | Text search vector for keyword searches |

### The Flow
1.  **User Query** -> **Router (Llama 3):** Decides whether to run an `sql` or `vector` search.
2.  **Tool Execution:**
    * *If SQL:* Executes precise filters (`code`, `title_like`) with `OR` logic support.
    * *If Vector:* Generates local embedding and finds nearest semantic neighbors.
3. **Smart Expansion:** If there's any chunked content like a `web page`, then an sql query is ran to get all of it's related pairs. This is done for the top N distinct chunked contents. Related pairs are then added to the search result.
4. **Reranking:** Jina AI reranks the recieved chunks and returns top N results
5.  **Context Building:** Combines recieved text content + parsed metadata fields.
6.  **Synthesis:** Groq (Llama 3 70B) generates the final natural language response.

## ⚡ Setup & Run

### 1. Prerequisites
* Python 3.10+
* Docker & Docker Compose (for PostgreSQL + pgvector) *(Not needed if db is hosted somewhere else)*
* **Groq API Key** (LLM)
* **Jina AI API Key** (Reranker)

### 2. Environment Variables
Create a `.env` file in the `api/` folder:

```ini
# Database
DATABASE_URL=postgresql://postgres:password@localhost:5432/orbisdb

# LLM Provider (Groq)
LLM_PROVIDER=groq
GROQ_API_KEY=your_groq_api_key_here
GROQ_MODEL=llama-3.3-70b-versatile

# Reranker (Jina)
JINA_API_KEY=jina_...
```
### 3. Installation
```bash
cd api
# Create virtual env (optional but recommended)
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows

# Install dependencies
pip install -r requirements.txt
```
### 4. Running the Server
Run inside `api/` folder
```bash
uvicorn main:app --reload
```
The server will start at `http://127.0.0.1:8000`.

## 🧪 Usage Examples
You can test these queries via the API or your Frontend:

| Intent | Query Example | Used Tool |
| :--- | :--- | :--- |
| Comparison | "Compare CMPE 351 and 321" | `SQL` (Batch Code) |
| Broad List | "List all computer courses" | `SQL` (Title Like) |
| Specific Info | "What is the ECTS of CMPE 460?" | `SQL` (Exact Code) |
| Fuzzy/General | "How is the campus life?" | `Vector` |
| Turkish | "Bilgisayar mühendisliği mezuniyet şartları..." | `Vector` (TR) |
