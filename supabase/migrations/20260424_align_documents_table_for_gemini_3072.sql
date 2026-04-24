-- Align the documents table with LangChain SupabaseVectorStore and Gemini 3072-dim embeddings.
-- This migration:
-- 1. ensures UUID ids (LangChain generates string UUID ids)
-- 2. stores embeddings as vector(3072)
-- 3. recreates match_documents for exact cosine search
--
-- Note: pgvector cannot create ivfflat/hnsw indexes on vector columns over 2000 dims.
-- So this migration intentionally uses exact search with no ANN index.
--
-- Warning: this drops and recreates the documents table.

create extension if not exists vector;
create extension if not exists pgcrypto;

drop function if exists match_documents(vector(768), int, jsonb);
drop function if exists match_documents(vector(3072), int, jsonb);
drop function if exists match_documents(vector, int, jsonb);

drop table if exists documents;

create table documents (
  id uuid primary key default gen_random_uuid(),
  content text,
  metadata jsonb,
  embedding vector(3072)
);

create or replace function match_documents(
  query_embedding vector(3072),
  match_count int default 5,
  filter jsonb default '{}'::jsonb
)
returns table (
  id uuid,
  content text,
  metadata jsonb,
  embedding vector(3072),
  similarity float
)
language plpgsql
as $$
begin
  return query
  select
    documents.id,
    documents.content,
    documents.metadata,
    documents.embedding,
    1 - (documents.embedding <=> query_embedding) as similarity
  from documents
  where documents.metadata @> filter
  order by documents.embedding <=> query_embedding
  limit match_count;
end;
$$;
