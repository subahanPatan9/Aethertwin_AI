import os
import time
import threading
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from app.core import config
from app.repositories.db_repo import db

router = APIRouter(tags=["system"])
start_time = time.time()

@router.get("/")
def read_root():
    return {
        "status": "ONLINE",
        "service": "AetherTwin Industrial Intelligence API",
        "version": "1.0.0"
    }

@router.get("/health")
def health_check():
    return {
        "status": "HEALTHY",
        "database_connected": db.use_mongo,
        "active_threads": threading.active_count()
    }

@router.get("/metrics")
def get_metrics():
    return {
        "uptime_seconds": round(time.time() - start_time, 1),
        "active_sessions": 1,
        "total_predictions_logged": len(db.get_audit_logs())
    }

# Serve compiled Angular static files in production mode
frontend_dist = os.path.abspath(os.path.join(config.BASE_DIR, "..", "frontend", "dist", "frontend", "browser"))

if os.path.exists(frontend_dist):
    @router.get("/{path_name:path}")
    def serve_frontend(path_name: str):
        # Prevent intercepting API routes, and redirect swagger/openapi requests to their exact built-in handlers
        p = path_name.lower().strip("/")
        if path_name.startswith("api/"):
            raise HTTPException(status_code=404, detail="API route not found")
        if p in ["docs", "redoc", "openapi.json"]:
            from fastapi.responses import RedirectResponse
            return RedirectResponse(url=f"/{p}")
            
        # Check if file exists in Angular build output
        file_path = os.path.join(frontend_dist, path_name)
        if os.path.exists(file_path) and os.path.isfile(file_path):
            return FileResponse(file_path)
            
        # Fallback to index.html for Single Page Application client routing
        index_path = os.path.join(frontend_dist, "index.html")
        if os.path.exists(index_path):
            return FileResponse(index_path)
            
        raise HTTPException(status_code=404, detail="Static index.html not found")
