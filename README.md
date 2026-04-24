# AI PDF Chatbot with FastAPI and Next.js

This monorepo contains a Next.js frontend and a FastAPI backend for uploading PDFs, indexing them in Supabase, and chatting over their contents with Google Gemini-powered retrieval.

## Architecture

- `frontend/`: Next.js app and UI
- `frontend/app/api/*`: thin proxy routes from the UI to the backend
- `backend/app/`: FastAPI app for threads, PDF ingestion, retrieval, and SSE chat streaming
- `backend/app/documents.py`: PDF parsing and chunking
- `backend/app/retrieval.py`: Supabase vector search plus answer generation
- `legacy_backend/`: archived TypeScript/LangGraph backend files moved out of the active Python backend

## Prerequisites

- Node.js 18+
- Python 3.11+
- A Supabase project with a `documents` table and `match_documents` function for vector similarity search
- Google Gemini API key

## Environment Variables

Create `backend/.env` from `backend/.env.example`:

```bash
cp backend/.env.example backend/.env
```

Key backend variables:

- `GOOGLE_API_KEY`
- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `GEMINI_CHAT_MODEL` default: `gemini-2.5-flash`
- `GEMINI_EMBEDDING_MODEL` default: `gemini-embedding-001`
- `GEMINI_EMBEDDING_DIMENSIONS` default: `3072`
- `RETRIEVAL_K` default: `5`
- `CHUNK_SIZE` default: `1500`
- `CHUNK_OVERLAP` default: `250`
- `CORS_ORIGINS` default: `http://localhost:3000`
- `SQLITE_PATH` default: `data/chat.sqlite3`

Create `frontend/.env` from `frontend/.env.example`:

```bash
cp frontend/.env.example frontend/.env
```

Key frontend variables:

- `BACKEND_API_URL=http://localhost:8000`
- `NEXT_PUBLIC_BACKEND_API_URL=http://localhost:8000`

## Local Development

Install frontend dependencies from the repo root:

```bash
yarn install
```

Install backend dependencies:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Run the backend:

```bash
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Run the frontend:

```bash
cd frontend
yarn dev
```

The frontend runs on `http://localhost:3000` and the backend runs on `http://localhost:8000`.

## API Overview

- `POST /threads`: create a chat thread
- `GET /threads/{thread_id}`: load persisted thread messages
- `POST /ingest`: upload up to 5 PDFs and index them in Supabase
- `POST /chat/stream`: stream chat responses as SSE
- `GET /health`: health check

## Supabase Vector Size

Gemini embeddings default to `3072` dimensions in this backend. Your Supabase `documents.embedding` column and `match_documents` function must use the same size.

If your current table is still using `768`, run the SQL in:

- `supabase/migrations/20260424_align_documents_table_for_gemini_3072.sql`

This migration recreates the `documents` table with `id uuid`, `embedding vector(3072)`, and a compatible `match_documents` RPC function for exact cosine search.

## Notes

- Threads and chat messages are persisted in SQLite on the FastAPI side.
- Indexed PDF chunks persist in Supabase.
- The active backend runtime is FastAPI in `backend/`.
- The older TypeScript/LangGraph backend code now lives in `legacy_backend/` for reference.
- The frontend uses Yarn; the backend is run directly with Python and `uvicorn`.
