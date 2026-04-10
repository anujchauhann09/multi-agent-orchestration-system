# v2 Implementation Notes

**Version:** 2.0.0
**Date:** 10 April 2026
**Status:** Completed
**Based on:** [v1 Implementation](https://github.com/anujchauhann09/multi-agent-orchestration-system/blob/main/docs/v1-implementation.md)

---

## What Changed in v2

v2 focused entirely on reliability, correctness, and security improvements to the existing pipeline. No new features were added — all changes address known gaps identified in v1.

---

## Improvements Delivered

### 1. Relative Import Resolution in AST Dependency Resolver

**File:** `backend/app/services/code_context_service.py`

**Problem:** v1's AST parser ignored relative imports (`from . import x`, `from ..core import y`), causing missed dependencies in package-structured repos.

**Solution:** Added `_resolve_relative_import()` which takes the current file's path and resolves relative imports using `posixpath` directory traversal.

```python
# v1 — relative imports silently ignored
elif isinstance(node, ast.ImportFrom):
    if node.module:
        imported_modules.append(node.module.replace(".", "/"))

# v2 — relative imports resolved using file path context
elif isinstance(node, ast.ImportFrom):
    if node.level and node.level > 0:
        candidates += _resolve_relative_import(current_file, node.level, node.module)
    elif node.module:
        ...
```

Each level of `.` traverses one directory up from the current file's location. `from ..core import config` in `app/auth/views.py` now correctly resolves to `app/core/config.py`.

---

### 2. Token Budget Cap on LLM Context

**Files:** `backend/app/services/code_context_service.py`, `backend/app/core/settings.py`

**Problem:** No upper bound on context size sent to LLM. Large repos with many transitive dependencies could produce prompts exceeding model limits or causing high cost.

**Solution:** Added `cap_context()` which trims the context list to fit within a configurable token budget. Planned files (highest priority) are always included first — only lower-priority files are dropped.

```python
# Estimate: ~4 characters per token (reliable approximation for code)
def _estimate_tokens(text: str) -> int:
    return len(text) // _CHARS_PER_TOKEN
```

Default cap: `MAX_CONTEXT_TOKENS = 6000` (configurable via `.env`). Applied as the final step in `build_context()` before returning to the agent.

---

### 3. Repo File Cache by Commit SHA

**File:** `backend/app/services/github_service.py`

**Problem:** Every task re-fetched all repo files from GitHub API regardless of whether the repo had changed. Slow and wasteful for multiple tasks on the same repo.

**Solution:** Added `get_repo_files_cached()` which:
1. Fetches the latest commit SHA (single lightweight API call)
2. Uses `sha256(repo_url + sha)` as a Redis cache key
3. Returns cached files on hit, fetches and caches on miss

```
Cache key: sha256("https://github.com/owner/repo:abc123def...")
TTL: 6 hours
```

Cache invalidation is automatic — a new commit changes the SHA, which changes the key, forcing a fresh fetch. Two tasks on the same repo at the same commit share one cached fetch.

`node_read_code` in `nodes.py` updated to call `get_repo_files_cached` instead of `get_repo_files`.

---

### 4. Unique Branch Names to Prevent Collision

**File:** `backend/app/domain/graph/nodes.py`

**Problem:** Branch name `agent/fix-task-{id}` was static. Retrying a task would attempt to create an already-existing branch on GitHub, causing a 422 error.

**Solution:** Branch name now includes retry count and Unix timestamp:

```
agent/fix-task-{task_id}-r{retry_count}-{unix_timestamp}

Example: agent/fix-task-3-r0-1744171234
```

Guaranteed unique on every run — no collision possible even across retries.

---

### 5. API Key Authentication Middleware

**Files:** `backend/app/core/middleware.py`, `backend/app/core/settings.py`, `backend/app/main.py`

**Problem:** All API endpoints were publicly accessible with no authentication.

**Solution:** Added `APIKeyMiddleware` (Starlette `BaseHTTPMiddleware`) that validates the `X-API-Key` header on all protected routes.

```
Header: X-API-Key: your-secret-key
```

Behavior:
- If `API_KEY` is not set in `.env` → middleware is bypassed (local dev mode)
- Public paths (`/health`, `/docs`, `/openapi.json`, `/redoc`) → always allowed
- All other paths → require valid `X-API-Key` header, return `401` on failure

Configured via `API_KEY` in `.env`.

---

### 6. Lifespan Handler Replaces Deprecated `on_event`

**File:** `backend/app/main.py`

**Problem:** FastAPI's `@app.on_event("startup")` is deprecated in newer versions and will be removed.

**Solution:** Replaced with the recommended `asynccontextmanager` lifespan pattern:

```python
# v1
@app.on_event("startup")
def on_startup():
    init()

# v2
@asynccontextmanager
async def lifespan(app: FastAPI):
    init()
    yield

app = FastAPI(lifespan=lifespan)
```

Code before `yield` runs on startup, code after `yield` runs on shutdown — enabling clean resource teardown in future if needed.

---

## Settings Added in v2

| Variable           | Default | Purpose                                  |
|--------------------|---------|------------------------------------------|
| MAX_CONTEXT_TOKENS | 6000    | Token budget cap for LLM context         |
| API_KEY            | ""      | API key for endpoint authentication      |

---

## Files Changed

| File                                        | Change                                      |
|---------------------------------------------|---------------------------------------------|
| `app/services/code_context_service.py`      | Relative import resolution + token cap      |
| `app/services/github_service.py`            | Repo file caching by commit SHA             |
| `app/domain/graph/nodes.py`                 | Unique branch names + cached file fetch     |
| `app/core/settings.py`                      | Added MAX_CONTEXT_TOKENS, API_KEY           |
| `app/core/middleware.py`                    | New — API key authentication middleware     |
| `app/main.py`                               | Lifespan handler, middleware registration   |

---

## Remaining Gaps (Carried from v1)

- Only Python files supported (no JS/TS/Go)
- Dynamic imports (`importlib.import_module`) not detected
- Docker test execution runs code as script, not pytest
- No per-task token usage or cost tracking
- No Alembic migrations (still using `create_all`)

---

## What Could Be Improved in v3

### Medium Term
- Run `pytest` inside Docker instead of executing code as a script
- Install `requirements.txt` inside Docker test container before running
- Support JS/TS import parsing via regex for multi-language repos
- Add Flower dashboard for Celery task monitoring
- Replace `Base.metadata.create_all` with Alembic migrations
- Add per-task token usage tracking and cost estimation

### Long Term
- Replace AST import parsing with LSP for symbol-level resolution
- Add Tree-sitter for accurate multi-language AST support
- Human-in-the-loop approval step between plan and code generation
- Kubernetes deployment with horizontal worker autoscaling
- GitHub webhook support to auto-trigger on issue creation
