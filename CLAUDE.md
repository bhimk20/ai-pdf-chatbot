# CLAUDE.md

## Project Snapshot

- Monorepo for AI PDF chat
- Active backend: FastAPI in `backend/`
- Active frontend: Next.js in `frontend/`
- Old TS/LangGraph backend moved to `legacy_backend/`
- Vector store: Supabase / pgvector
- Model provider: Google Gemini

## Current Architecture

- Frontend uploads PDFs through `frontend/app/api/ingest/route.ts`
- Frontend creates thread through `frontend/app/api/thread/route.ts`
- Frontend chats through `frontend/app/api/chat/route.ts`
- Those Next routes proxy to FastAPI
- FastAPI entrypoint: `backend/app/main.py`
- PDF parsing/chunking: `backend/app/documents.py`
- Retrieval: `backend/app/retrieval.py`

## Important Constraints

- Run backend with Python directly, not Yarn
- Run frontend with Node package manager in `frontend/`
- Supabase `documents` table must match current backend expectations
- `documents.id` should be `uuid`
- `documents.embedding` should be `vector(3072)`
- Current retrieval uses exact search RPC, not pgvector ANN index
- `vector(3072)` cannot use `ivfflat` / `hnsw` index directly

## Runbook

### Backend

```bash
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

## Required Env

### backend/.env

- `GOOGLE_API_KEY`
- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `GEMINI_CHAT_MODEL=gemini-2.5-flash`
- `GEMINI_EMBEDDING_MODEL=gemini-embedding-001`
- `GEMINI_EMBEDDING_DIMENSIONS=3072`

### frontend/.env

- `BACKEND_API_URL=http://localhost:8000`
- `NEXT_PUBLIC_BACKEND_API_URL=http://localhost:8000`

## Supabase Expectations

Run the migration in:

- `supabase/migrations/20260424_align_documents_table_for_gemini_3072.sql`

This repo currently expects:

- table: `documents`
- columns: `id uuid`, `content text`, `metadata jsonb`, `embedding vector(3072)`
- rpc: `match_documents(query_embedding vector(3072), match_count int, filter jsonb)`

## Token-Minimizing Rules

- Prefer terse answers over tutorials
- State only: cause, fix, next step
- Do not restate logs unless needed
- Do not explain obvious framework basics
- Prefer file paths and commands over prose
- If editing, edit first, explain second
- If blocked, ask one sharp question only

## Cave Man Communication

Use compressed phrases when context is already shared.

Examples:

- `thread 500. backend dead. start uvicorn.`
- `upload fail. db dim bad. fix supabase vector 3072.`
- `retrieval broken. supabase client mismatch. rpc direct.`
- `frontend ok. backend env bad. service role key wrong.`

Pattern:

- `problem -> cause -> action`
- omit filler words
- omit politeness fluff in working mode
- use fragments, not paragraphs

Good:

- `chat fail. no thread. /threads 500. check backend health.`

Bad:

- `It seems like there may possibly be a problem with the backend server configuration.`

## Suggested Low-Token Shortcodes

- `BE` = backend
- `FE` = frontend
- `SB` = Supabase
- `ENV` = environment variables
- `RPC` = `match_documents`
- `DIM` = embedding dimensions
- `SRK` = service role key
- `UP` = upload / ingest
- `RET` = retrieval
- `MSG` = chat message path

Examples:

- `BE up? curl /health`
- `UP fail. SB DIM mismatch`
- `RET fail. RPC schema off`
- `SRK wrong. use service role not publishable`

## Good Workflow For Future Sessions

1. Check `curl http://localhost:8000/health`
2. Check `frontend/.env` and `backend/.env`
3. Check Supabase schema and RPC
4. Reproduce with smallest failing action
5. Patch code or SQL
6. Restart backend
7. Re-test from UI

## Avoid

- Reintroducing LangGraph into active backend
- Mixing Python backend runtime with Yarn wrappers
- Using publishable Supabase keys for backend writes
- Creating ANN indexes on `vector(3072)`
- Long explanations when a command or patch is enough

## If Optimizing Further

- Add a `Makefile` with short commands: `be`, `fe`, `test`, `health`
- Add a tiny `/debug/config` route for non-secret runtime checks
- Add backend startup validation for env + Supabase RPC existence
- Add a smoke test script for `/threads`, `/ingest`, `/chat/stream`
- Add structured error messages in frontend toast handling
