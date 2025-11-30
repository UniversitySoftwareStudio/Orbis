# Data Ingestion Scripts

## ⚠️ Temporary/Utility Scripts

This directory contains **standalone ingestion scripts** for populating the database with initial data. These scripts are:

- **Not part of the main application architecture**
- **Temporary/utility scripts** that can be modified or removed as needed
- **Self-contained** - duplicate models and dependencies to run independently
- **Meant for initial setup or one-time data imports**

## Purpose

These scripts exist to quickly populate the database during development or deployment. They are NOT modular, NOT part of the service layer, and should NOT be used as a reference for application architecture.

## Current Scripts

### `ingest.py`
Standalone script to load course data with embeddings into the database.

**Usage:**
```bash
cd api/database/ingest
python3 ingest.py example_courses.json
```

**What it does:**
1. Loads JSON file with course data
2. Generates embeddings using SentenceTransformer
3. Inserts courses and content into database
4. Self-contained with its own model definitions

**Why it's standalone:**
- Runs independently of the API server
- Can be executed before app is fully configured
- No dependency on application imports
- Duplicates models to avoid circular imports

## When to Use

✅ Initial database population  
✅ Bulk data imports during development  
✅ One-time migration scripts  
✅ Testing data setup  

## When NOT to Use

❌ Regular application data flow (use repositories instead)  
❌ API endpoints for data creation (use routes → services → repositories)  
❌ Production data management (use proper admin tools)  

## Modifying or Removing

Feel free to:
- Modify scripts for your specific data format
- Add new ingestion scripts for different data types
- Remove this entire directory once initial setup is complete
- Replace with more robust ETL tools for production

## Architecture Note

**This is NOT following the clean architecture of the rest of the app.**  
The main app uses: Routes → Services → Repositories → Database

Ingestion scripts bypass this entirely - they're just utility scripts.
