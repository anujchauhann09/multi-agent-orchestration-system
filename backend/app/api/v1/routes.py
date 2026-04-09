from fastapi import APIRouter
from app.api.v1.endpoints import workflow, status, logs

api_router = APIRouter()

api_router.include_router(workflow.router, prefix="/workflow", tags=["workflow"])
api_router.include_router(status.router, prefix="/status", tags=["status"])
api_router.include_router(logs.router, prefix="/logs", tags=["logs"])
