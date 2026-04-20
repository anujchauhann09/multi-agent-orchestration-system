# Multi-Agent Orchestration System

An AI-powered backend that autonomously resolves GitHub issues — it reads the issue, plans a fix, writes code, tests it in an isolated Docker container, and opens a Pull Request. No human intervention required.

Built with a hybrid approach: LLM is used only where reasoning is required. Everything else — fetching files, resolving dependencies, running tests, creating PRs — is deterministic.

---

## How it works

```
Submit GitHub issue URL
        ↓
Planner Agent (LLM) — analyzes issue, produces execution plan
        ↓
Code Reader (deterministic) — fetches repo files, vector search, AST dependency resolution
        ↓
Code Writer Agent (LLM) — generates targeted fix using filtered context
        ↓
Test Writer Agent (LLM) — generates isolated pytest unit tests
        ↓
Docker Executor (deterministic) — runs tests in sandboxed container
        ↓
Tests pass → Pull Request opened on GitHub
Tests fail → Fix Agent (LLM, max 2 retries) → retry
Max retries exceeded → Dead Letter Queue
```

LLM is called in exactly 3 places: planning, code generation, and error fixing. Everything else runs without AI.

---

## Tech Stack

| Layer | Technology |
|---|---|
| API | FastAPI + Uvicorn |
| Task Queue | Celery 5 + Redis |
| Workflow | LangGraph |
| LLM | Google Gemini (gemini-2.5-flash) |
| Embeddings | Google Gemini (gemini-embedding-001) |
| Vector DB | Pinecone |
| Database | PostgreSQL 15 + SQLAlchemy 2 |
| GitHub | PyGithub |
| Code Execution | Docker (sandboxed containers) |
| Reverse Proxy | Nginx |
| Language | Python 3.11 |

---

## Prerequisites

- Docker and Docker Compose
- Google API key ([Google AI Studio](https://aistudio.google.com))
- GitHub personal access token (with `repo` scope)
- Pinecone account and index (dimension: 768)

---

## Setup

**1. Clone the repository**

```bash
git clone https://github.com/anujchauhann09/multi-agent-orchestration-system.git
cd multi-agent-orchestration-system
```

**2. Create `.env` at the project root**

```env
DATABASE_URL=postgresql://postgres:postgres@postgres:5432/multiagent_db
REDIS_URL=redis://redis:6379/0

GOOGLE_API_KEY=your_google_api_key
GOOGLE_API_MODEL=gemini-2.5-flash
GOOGLE_EMBEDDING_MODEL=models/gemini-embedding-001
GOOGLE_API_MODEL_TESTER=gemini-2.5-flash-lite

GITHUB_TOKEN=your_github_token

PINECONE_API_KEY=your_pinecone_api_key
PINECONE_INDEX=your_index_name

API_KEY=your_secret_api_key
```

**3. Start all services**

```bash
docker-compose up --build
```

**4. Verify**

```bash
curl http://localhost/health
```

---

## Usage

**Submit a GitHub issue for fixing:**

```bash
curl -X POST http://localhost/api/v1/workflow/submit \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your_secret_api_key" \
  -d '{
    "issue_url": "https://github.com/owner/repo/issues/1",
    "repo_url": "https://github.com/owner/repo"
  }'
```

**Poll task status:**

```bash
curl http://localhost/api/v1/workflow/{task_uuid}/status \
  -H "X-API-Key: your_secret_api_key"
```

**View task logs:**

```bash
curl http://localhost/api/v1/logs/{task_uuid}/logs \
  -H "X-API-Key: your_secret_api_key"
```

**Retry a failed task:**

```bash
curl -X POST http://localhost/api/v1/workflow/{task_uuid}/retry \
  -H "X-API-Key: your_secret_api_key"
```

Interactive API docs available at `http://localhost/docs`

---

## API Reference

| Method | Endpoint | Description |
|---|---|---|
| POST | /api/v1/workflow/submit | Submit a GitHub issue |
| GET | /api/v1/workflow/{uuid}/status | Poll task status |
| POST | /api/v1/workflow/{uuid}/retry | Retry a failed task |
| GET | /api/v1/status/tasks | List all tasks |
| GET | /api/v1/logs/{uuid}/logs | Get task logs |
| GET | /health | Health check |

All endpoints except `/health` and `/docs` require the `X-API-Key` header.

---

## Architecture

![System Workflow](docs/multi-agent-orchestration-system-workflow.png)

---

## Key Design Decisions

**LLM used minimally** — only for planning, code generation, and error fixing. Fetching files, resolving imports, running tests, and creating PRs are all deterministic. This reduces cost, latency, and unpredictability.

**AST dependency resolution** — when the planner identifies files to modify, the system uses Python AST parsing to trace all import dependencies and include them in the LLM context. The LLM never sees the full repo — only relevant files.

**Vector search for context** — all repo files are embedded into Pinecone. Semantic search finds additional relevant files beyond what the planner explicitly identified.

**Token budget cap** — context sent to LLM is capped at 6000 tokens (configurable). Planned files take priority; lower-priority files are dropped if the budget is exceeded.

**Redis caching** — planner responses are cached 24h by prompt hash. Repo files are cached by commit SHA. Same issue or same commit = zero redundant API calls.

**Sandboxed execution** — generated code runs in an isolated Docker container with memory limits and no network access during test execution. The container is destroyed after each run.

**Dead Letter Queue** — tasks that fail after max retries are moved to a DLQ for manual inspection and retry, not silently dropped.

---

## Project Structure

```
multi-agent-orchestration-system/
├── backend/
│   ├── app/
│   │   ├── api/v1/endpoints/     # REST endpoints
│   │   ├── core/                 # settings, celery, middleware
│   │   ├── db/                   # session, init
│   │   ├── domain/
│   │   │   ├── agents/           # planner, code_writer, test_writer, fix_agent
│   │   │   ├── graph/            # LangGraph nodes and workflow
│   │   │   └── state/            # shared workflow state
│   │   ├── infrastructure/
│   │   │   ├── docker/           # sandboxed test executor
│   │   │   └── queue/            # redis client
│   │   ├── models/               # SQLAlchemy ORM models
│   │   ├── repositories/         # database query layer
│   │   ├── schemas/              # Pydantic models
│   │   ├── services/
│   │   │   ├── llm_service.py        # Gemini + Redis cache + retry
│   │   │   ├── github_service.py     # GitHub API
│   │   │   ├── embedding_service.py  # Pinecone vector ops
│   │   │   └── code_context_service.py # AST dep resolver
│   │   └── tasks/                # Celery task definitions
│   ├── Dockerfile
│   └── Dockerfile.worker
├── frontend/
│   ├── src/
│   └── Dockerfile                # two-stage: Node build → Nginx serve
├── infrastructure/
│   └── nginx/
│       └── nginx.conf
├── docs/
│   ├── v1-implementation.md
│   └── v2-implementation.md
└── docker-compose.yml
```

---

## Database Schema

| Table | Purpose |
|---|---|
| tasks | Central task lifecycle (status, step, retries, PR URL) |
| task_steps | Per-agent step tracking with input/output |
| task_logs | Partitioned structured logs (RANGE by month) |
| task_results | Final generated code and test cases |
| dlq_tasks | Dead letter queue for failed tasks |
| workflow_states | Resumable LangGraph state |

---

## Implementation Notes

Detailed notes on what was built, known gaps, and improvement roadmap:

- [v1 Implementation](docs/v1-implementation.md) — initial pipeline
- [v2 Implementation](docs/v2-implementation.md) — reliability and security improvements

---

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature`
3. Commit using conventional commits: `feat:`, `fix:`, `chore:`, `docs:`
4. Open a Pull Request

---

## License

Open source under the [MIT License](https://opensource.org/licenses/MIT).
