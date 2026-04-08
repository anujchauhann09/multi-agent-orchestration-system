from fastapi import FastAPI
from app.db.init_db import init

app = FastAPI(title="Multi-Agent Orchestration System")


@app.on_event("startup")
def on_startup():
    init()


@app.get("/health")
def health():
    return {"status": "ok"}
