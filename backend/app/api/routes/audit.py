from fastapi import APIRouter
from app.repositories.db_repo import db

router = APIRouter(prefix="/api/audit", tags=["audit"])

@router.get("/logs")
def get_audit_trail():
    return db.get_audit_logs()
