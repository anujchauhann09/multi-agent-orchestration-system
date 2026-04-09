from fastapi import FastAPI
from app.db.init_db import init
from app.api.v1.routes import api_router

app = FastAPI(title="Multi-Agent Orchestration System")


@app.on_event("startup")
def on_startup():
    init()


app.include_router(api_router, prefix="/api/v1")


@app.get("/health")
def health():
    return {"status": "ok"}
