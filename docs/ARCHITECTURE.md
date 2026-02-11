# Architecture (MVP -> Production)

## Goals
- Small-team RAG/Agent RAG platform
- PDF-only ingestion (MVP)
- Agent + MCP/function calling
- Evaluation: TruLens + RAGAS

## End-to-end chain
1. Upload (PDF)
2. Parse -> clean -> chunk
3. Embed -> vector index
4. Retrieve (hybrid) -> rerank -> filter (RBAC/ACL)
5. Answer + citations
6. Evaluation -> feedback -> iteration

## Services (MVP)
- `api` (FastAPI): upload, ingestion, retrieval, chat, admin
- `frontend` (Streamlit): upload, chat, evaluation UI
- `vector` (Qdrant)
- `db` (Postgres): metadata, users, ACL
- `object` (MinIO): raw files

## Data stores
- Postgres: users, teams, documents, chunks, eval runs
- Qdrant: embeddings + metadata
- MinIO: raw PDFs

## Security
- Team-level RBAC (MVP)
- Doc-level ACL + tags
- Audit log (later)

## Agent
- Tooling: function calling + MCP bridge
- Tools: search_docs, fetch_doc, reindex, evaluate

## Evaluation
- Offline batch: RAGAS / TruLens
- Online: feedback + sampling
