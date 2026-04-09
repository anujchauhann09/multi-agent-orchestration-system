# v1 Implementation Notes

**Version:** 1.0.0
**Date:** 09 April 2026
**Status:** Completed

---

## What Was Built

### Infrastructure
- Docker Compose setup with 4 services: FastAPI backend, Celery worker, PostgreSQL, Redis
- PostgreSQL schema with 6 tables, composite indexes, and monthly partitioned `task_logs`
- Celery with 3 dedicated queues: `main_queue`, `retry_queue`, `dlq_queue`
- Redis used as both message broker and LLM response cache

### Agent Pipeline (LangGraph)
A 7-node directed graph handling the full issue-to-PR workflow:

| Node         | Type          | What it does                                      |
|--------------|---------------|---------------------------------------------------|
| plan         | LLM           | Analyzes issue, produces structured execution plan |
| read_code    | Deterministic | Fetches repo, embeds files, resolves dependencies  |
| write_code   | LLM           | Generates targeted code fix from plan + context   |
| execute      | Deterministic | Runs generated code in isolated Docker container  |
| fix          | LLM (limited) | Fixes code based on parsed error, max 2 retries   |
| create_pr    | Deterministic | Commits changes and opens GitHub Pull Request     |
| dlq          | Deterministic | Marks task failed, sends to dead letter queue     |

### LLM Optimization Strategy
- LLM called in exactly 3 places (plan, write, fix)
- Planner responses cached in Redis for 24 hours by prompt hash
- Context sent to LLM is pre-filtered — not the full repo
- Fix agent receives capped error output (2000 chars max)
- Hard retry cap of 2 — no infinite LLM loops

### Code Context Strategy
The most significant engineering decision in v1.

Instead of sending the full repo to the LLM:
1. Planner identifies `files_to_modify`
2. AST parses imports from those files to find local dependencies
3. Transitive resolution up to 3 levels deep
4. Vector search (Pinecone) adds semantically relevant files not caught by AST
5. Results deduplicated — planned files take priority

This means the LLM receives only the files it actually needs.

### Services
- `llm_service.py` — Gemini API calls with Redis caching layer
- `github_service.py` — fetch issues, repo files, create branches and PRs
- `embedding_service.py` — Pinecone upsert, vector search, namespace cleanup
- `code_context_service.py` — AST dependency resolver + context builder

### Database Layer
- Repository pattern — all DB queries isolated in `repositories/`
- Per-step status updates written to DB during workflow execution
- Task logs written at each node transition for full observability
- Workflow state persisted in `workflow_states` table for resumability

### API
- `POST /api/v1/workflow/submit` — accepts issue + repo URL, queues task
- `GET /api/v1/workflow/{uuid}/status` — returns current step and status
- `POST /api/v1/workflow/{uuid}/retry` — re-queues a failed task
- `GET /api/v1/logs/{uuid}/logs` — returns all logs for a task
- `GET /api/v1/status/tasks` — lists tasks filtered by status

---

## Known Gaps

### 1. Relative imports not fully resolved
AST resolver handles absolute imports correctly. Relative imports
(`from . import x`, `from ..core import y`) need path-aware resolution
for deeply nested package structures.

### 2. Python only
`get_repo_files()` fetches `.py` files only. Multi-language repos are not supported.

### 3. No token budget cap
Context size sent to LLM is not bounded by token count. A file with many
transitive dependencies could produce a very large prompt.

### 4. Dynamic imports not detected
```python
importlib.import_module("utils")  # AST cannot detect this
```

### 5. No dependency graph caching
Every task re-fetches and re-parses the entire repo from GitHub API.
For large repos this adds significant latency.

### 6. Basic Docker test execution
The executor runs generated code as a Python script. It does not:
- Install project dependencies before running
- Execute existing test files (pytest)
- Handle multi-file project structures properly

### 7. Branch collision on retry
Retrying a task attempts to create `agent/fix-task-{id}` which already
exists on GitHub, causing the branch creation to fail.

### 8. No API authentication
All endpoints are publicly accessible. No API key or JWT protection.

### 9. `on_event("startup")` deprecation
FastAPI's `@app.on_event("startup")` is deprecated in newer versions.
Should be replaced with lifespan context manager.

---

## What Could Be Improved

### Short Term
- Resolve relative imports in `code_context_service.py` using file path context
- Add token count cap before sending context to LLM
- Cache dependency graph per repo + commit SHA in Redis
- Append timestamp or retry count to branch name to avoid collision
- Add API key authentication middleware
- Replace `on_event("startup")` with lifespan handler

### Medium Term
- Run `pytest` inside Docker instead of executing code as a script
- Install `requirements.txt` inside Docker test container before running
- Support JS/TS import parsing via regex for multi-language repos
- Add Flower dashboard for Celery task monitoring
- Replace `Base.metadata.create_all` with Alembic migrations
- Add per-task token usage tracking and cost estimation

### Long Term
- Replace AST import parsing with LSP (Language Server Protocol)
  for symbol-level dependency resolution
- Add Tree-sitter for accurate multi-language AST support
- Implement human-in-the-loop approval step between plan and code generation
- Kubernetes deployment with horizontal worker autoscaling
- Add webhook support so GitHub issues auto-trigger the workflow
