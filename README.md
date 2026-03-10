# Orbis (SIS & RAG System)

An intelligent Student Information System (SIS) designed for Istanbul Bilgi University. This project integrates a traditional administrative backend with an advanced **RAG (Retrieval-Augmented Generation)** chatbot, allowing students to query course catalogs, university regulations, and administrative procedures in natural language.

![Status](https://img.shields.io/badge/Status-Prototype-orange)
![Tech](https://img.shields.io/badge/Stack-FastAPI_|_PostgreSQL_|_Angular-blue)

## 🌟 Key Features

### 🧠 Advanced RAG Pipeline (Double Reranking)
Unlike standard RAG systems, UniChat uses a multi-stage retrieval process to ensure high precision:
1.  **Hybrid Search:** Retrieves N candidates using Vector Similarity (Semantic) + PostgreSQL `tsvector` (Keyword).
2.  **Pre-Expansion Rerank:** Uses Jina AI to identify the "True Top N" documents from the initial pool.
3.  **Smart Context Expansion:** Fetches neighboring chunks *only* for those top N documents to provide full context (e.g., the whole regulation article).
4.  **Final Rerank:** Re-scores the expanded context (N chunks) to feed the absolute best data to the LLM.

### ⚡ Stateless & Scalable
* **Zero-History Context:** The RAG engine is stateless to prevent "Context Bloat" and token overflow (413 errors).
* **Strict Router:** An intelligent router prevents SQL overload by detecting generic queries ("Staj") and routing them to Vector search, reserving SQL only for specific Course Code lookups.

### 🎓 Student Information System (Planned)
* **Course Management:** CRUD operations for courses and sections.
* **Event System:** (Upcoming) Automated deadlines and regulation checks.
* **Submission Checks:** (Upcoming) Automated assignment validation.

## 🛠️ Tech Stack

* **Backend:** Python, FastAPI, SQLAlchemy
* **Database:** PostgreSQL with `pgvector` extension
* **LLM Engine:** Llama 3.3 70B (via Groq API)
* **Embeddings:** `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`
* **Reranker:** Jina AI
* **Frontend:** React
* **Infrastructure:** Docker, Docker Compose

## 🚀 Getting Started

### Prerequisites
* Docker & Docker Compose (Only to run db locally)
* Python 3.10+
* Groq API Key (for LLM)
* Jina AI API Key (for Reranking)

### Installation

1.  **Clone the repository:**
    ```bash
    git clone [https://github.com/your-username/unichat-agent.git](https://github.com/your-username/unichat-agent.git)
    cd unichat-agent
    ```

2.  **Set up Environment Variables:**
    Create a `.env` file in the `api/` directory:
    ```ini
    DB_NAME=postgres
    DB_USER=postgres
    DB_PASSWORD=yourpassword
    DB_HOST=db
    DB_PORT=5432
    GROQ_API_KEY=gsk_...
    JINA_API_KEY=jina_...
    ```
### How to Run

Details on how to run both front and backend of the project can be found at `api/README.md` and `web/README.md`

## 📂 Project Structure

* `api/`: FastAPI backend, RAG logic, and database scripts.
* `api/data/`: Raw PDF documents and scraped JSONL data.
* `api/scripts/`: Various scripts used to load and embed data into db.
* `web/`: Angular frontend application.

## ✅ Completed Milestones

* **Core RAG Architecture:** "One-Table" approach unifying Courses, Web Pages, and PDFs.
* **Data Pipeline:**
    * Scrapers for Courses (JSONL) and Web Pages.
    * PDF Pipeline: Hybrid cleaning and language detection.
* **Advanced Retrieval:**
    * **Intent Router:** Distinguishes between "List", "Compare", and "Explain" queries.
    * **Auto-Repair Logic:** Fixes malformed SQL queries automatically.
    * **Smart Expansion:** Fetches full context for relevant documents with soft diversity caps.
* **Persona & Safety:** "Reference Librarian" persona that enforces citations and strict administrative safety rules.

## 🚧 Roadmap

* [ ] Implement SIS Relational Tables (Students, Enrollments).
* [ ] Integrate Relational Data into RAG (Text-to-SQL for schedule/grades).
* [ ] Admin Dashboard for managing knowledge base.

## 🔑 Use Cases

### Chatbot

A RAG based chatbot system that has access to all non-sensitive university data that will be able to answer various queries of users (instructors & students alike)

### Submission Check

A simple AI based system that will compare a document submitted aganist a ruleset (something like submission guidelines - a good example can be a homework submission guide that an instructor has provided) to give information to the user before submission about whether the submission is valid or not.

### SIS Related

A "Student Information System". Students and instructors can login, there can be departments, courses, sections, registrations, rules & guidelines, etc. to provide a comprehensive online platform for entirety of a university.
