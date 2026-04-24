# TODO

## Current State

- Active backend: FastAPI in `backend/`
- Active frontend: Next.js in `frontend/`
- Chat threads/messages persist in SQLite
- Embeddings stored in Supabase
- Retrieval uses Supabase RPC `match_documents`
- Legacy TS/LangGraph backend moved to `legacy_backend/`

## Known Working

- Backend starts with `uvicorn`
- Frontend proxies through Next API routes
- Thread create/load flow exists
- Chat persistence exists in SQLite
- Supabase schema is aligned for `vector(3072)`

## Known Issues

- Gemini/Gemma integration has compatibility workarounds in `backend/app/retrieval.py`
- Model output normalization is still a sensitive area
- Supabase key must be service-role for backend writes
- Retrieval / answer flow still reflects PDF-chat design, not resume-tailoring design

## Tomorrow Tasks

- [ ] Decide v1 input/output for resume tailoring
- [ ] Replace PDF-chat mental model with single-resume tailoring flow
- [ ] Add JD parser:
  - skills
  - seniority
  - domain
  - must-haves
  - impact style
- [ ] Define one-resume/job-bank schema with metadata:
  - company
  - project
  - tags
  - tech
  - impact
  - role type
  - seniority
  - bullet atoms
- [ ] Build deterministic retrieval/ranking stage
- [ ] Retrieve only:
  - top 8 bullets
  - top 2 projects
  - top 1 summary variant
- [ ] Send only retrieved slices to LLM
- [ ] Add rewriting stage for tailored resume output
- [ ] Keep scope to one resume only for v1

## Resume Tailoring Direction

Two-stage pipeline:

1. Deterministic filtering/ranking
2. LLM rewriting

Target flow:

1. Parse JD
2. Pre-index one resume / job-bank atoms with metadata
3. Retrieve top relevant chunks only
4. Send only those chunks to LLM
5. Produce tailored resume output
