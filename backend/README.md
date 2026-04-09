# Multi-Agent Orchestration System — Backend

An AI-powered backend that autonomously resolves GitHub issues by planning, writing, testing, and submitting code fixes as Pull Requests — with minimal LLM usage through hybrid deterministic + AI execution.

---

## Overview

Submit a GitHub issue URL and the system handles the rest:

1. Analyzes the issue and creates an execution plan (LLM)
2. Fetches relevant source files using vector search + AST dependency resolution (deterministic)
3. Generates a targeted code fix (LLM)
4. Runs the fix in an isolated Docker container to verify it works (deterministic)
5. Opens a Pull Request with the fix (deterministic)

LLM is used in exactly 3 places — planning, code generation, and error fixing. Everything else is deterministic.

---

## Tech Stack

| Layer          | Technology                            |
|----------------|---------------------------------------|
| API            | FastAPI + Uvicorn                     |
| Task Queue     | Celery 5 + Redis                      |
| Workflow       | LangGraph                             |
| LLM            | Google Gemini (gemini-2.5-flash)      |
| Embeddings     | Google Gemini (gemini-embedding-001)  |
| Vector DB      | Pinecone                              |
| Database       | PostgreSQL 15 + SQLAlchemy 2          |
| GitHub         | PyGithub                              |
| Containers     | Docker + Docker Compose               |
| Language       | Python 3.11                           |

---

## Getting Started

### Prerequisites
- Docker and Docker Compose
- GitHub personal access token (with `repo` scope)
- Google API key (Gemini)
- Pinecone account and index (dimension: 768)

### Setup

1. Clone the repository and navigate to the project root.

2. Create a `.env` file at the project root:

```env
DATABASE_URL=postgresql://postgres:postgres@postgres:5432/multiagent_db
REDIS_URL=redis://redis:6379/0

GOOGLE_API_KEY=your_google_api_key
GOOGLE_API_MODEL=gemini-2.5-flash
GOOGLE_EMBEDDING_MODEL=models/gemini-embedding-001

GITHUB_TOKEN=your_github_token

PINECONE_API_KEY=your_pinecone_api_key
PINECONE_INDEX=your_index_name
```

3. Start all services:

```bash
docker-compose up --build
```

4. Verify everything is running:

```bash
curl http://localhost:8000/health
```

---

## API Reference

| Method | Endpoint                           | Description                  |
|--------|------------------------------------|------------------------------|
| POST   | /api/v1/workflow/submit            | Submit a GitHub issue        |
| GET    | /api/v1/workflow/{uuid}/status     | Poll task status             |
| POST   | /api/v1/workflow/{uuid}/retry      | Retry a failed task          |
| GET    | /api/v1/status/tasks               | List all tasks               |
| GET    | /api/v1/logs/{uuid}/logs           | Get logs for a task          |
| GET    | /health                            | Health check                 |

Interactive docs available at `http://localhost:8000/docs`

### Example

```bash
curl -X POST http://localhost:8000/api/v1/workflow/submit \
  -H "Content-Type: application/json" \
  -d '{
    "issue_url": "https://github.com/owner/repo/issues/1",
    "repo_url": "https://github.com/owner/repo"
  }'
```

---

## Architecture

```
FastAPI → Redis → Celery Worker → LangGraph
                                      ├── Planner (LLM)
                                      ├── Code Reader (deterministic)
                                      ├── Code Writer (LLM)
                                      ├── Docker Executor (deterministic)
                                      ├── Fix Agent (LLM, max 2 retries)
                                      └── PR Creator (deterministic)
                                              ↓
                                        PostgreSQL
```

---

## Project Structure

```
backend/
├── app/
│   ├── api/v1/endpoints/       # REST endpoints
│   ├── core/                   # settings, celery config
│   ├── db/                     # session, migrations
│   ├── domain/
│   │   ├── agents/             # planner, code_writer, fix_agent
│   │   ├── graph/              # LangGraph nodes and workflow
│   │   └── state/              # shared workflow state schema
│   ├── infrastructure/
│   │   ├── docker/             # sandboxed code executor
│   │   └── queue/              # redis client
│   ├── models/                 # SQLAlchemy ORM models
│   ├── repositories/           # database query layer
│   ├── schemas/                # Pydantic request/response models
│   ├── services/
│   │   ├── llm_service.py          # Gemini + Redis caching
│   │   ├── github_service.py       # GitHub API integration
│   │   ├── embedding_service.py    # Pinecone vector operations
│   │   └── code_context_service.py # AST dependency resolver
│   ├── tasks/                  # Celery task definitions
│   └── main.py                 # application entry point
├── Dockerfile
├── Dockerfile.worker
└── requirements.txt
```

---

## Implementation Notes

See [`docs/v1-implementation.md`](https://github.com/anujchauhann09/multi-agent-orchestration-system/blob/main/docs/v1-implementation.md) for detailed notes on what was built in v1, known gaps, and planned improvements.

---

## Contributing

1. Create a feature branch: `git checkout -b feature/your-feature`
2. Commit using conventional commits: `feat:`, `fix:`, `chore:`, `docs:`
3. Open a Pull Request

---

## License

Open source under the [MIT License](https://opensource.org/licenses/MIT).
