# Orbis (SIS & RAG System)

An intelligent Student Information System (SIS) designed for Istanbul Bilgi University. This project integrates a traditional administrative backend with an advanced **RAG (Retrieval-Augmented Generation)** chatbot, allowing students to query course catalogs, university regulations, and administrative procedures in natural language.

![Status](https://img.shields.io/badge/Status-Prototype-orange)
![Tech](https://img.shields.io/badge/Stack-FastAPI_|_PostgreSQL_|_Angular-blue)

## 🌟 Key Features

### 🧠 Intelligent Chatbot (RAG)
* **Hybrid Search:** Combines Vector Similarity (Semantic) + SQL `ts_rank` (Keyword) for high-precision retrieval.
* **Intent Decomposition:** Automatically detects if a user is asking for a comparison, a list, or a specific fact, and routes the query to the best tool (SQL vs. Vector).
* **One-Table Architecture:** Unifies Courses, Web Pages, and PDFs into a single searchable knowledge base.
* **Smart Reranking:** Uses Jina AI to rerank results, ensuring the most relevant answer is at the top.
* **Citation Engine:** Provides strict, clickable citations for every fact, distinguishing between entities (offices) and sources (documents).

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
* [ ] Event System for deadline tracking.
* [ ] Admin Dashboard for managing knowledge base.

## 🔑 Use Cases

### Chatbot

A RAG based chatbot system that has access to all non-sensitive university data that will be able to answer various queries of users (instructors & students alike)

### Event System

A RAG based system that will periodically check university regulations and course rules in order to create various events (like informing students a deadline of a homework/project submission, suggesting students to take actions such as registering to erasmus programmes, etc.)

### Submission Check

A simple AI based system that will compare a document submitted aganist a ruleset (something like submission guidelines - a good example can be a homework submission guide that an instructor has provided) to give information to the user before submission about whether the submission is valid or not.

### SIS Related

A "Student Information System". Students and instructors can login, there can be departments, courses, sections, registrations, rules & guidelines, etc. to provide a comprehensive online platform for entirety of a university.