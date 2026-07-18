import os
import time
import threading
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Service and Repository singletons
from app.repositories.db_repo import db
from app.services.telemetry.connectivity import daq_service

# Routers
from app.api.routes import (
    auth,
    telemetry,
    copilot,
    predictive,
    digital_twin,
    executive,
    approvals,
    work_order,
    maintenance,
    audit,
    system,
)

# Initialize FastAPI App
app = FastAPI(title="AetherTwin Backend Engine")

# Security & Header Protection Middleware with API versioning rewrite
@app.middleware("http")
async def security_hardening_middleware(request, call_next):
    path = request.scope.get("path", "")
    if path.startswith("/api/v1/"):
        request.scope["path"] = path.replace("/api/v1/", "/api/", 1)
        
    response = await call_next(request)
    
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    
    # Relax CSP for Swagger / ReDoc docs endpoints to allow CDNs and inline scripts
    if path in ["/docs", "/redoc", "/openapi.json"]:
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "img-src 'self' data: https://fastapi.tiangolo.com;"
        )
    else:
        response.headers["Content-Security-Policy"] = "default-src 'self'"
    return response

# Configure CORS with security hardening
allowed_origins = os.environ.get("ALLOWED_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Background Simulator Thread
def run_simulation_loop():
    print("Simulator: Background physical thread started.")
    while True:
        try:
            # Step the telemetry ingestion forward via DAQ
            telemetry = daq_service.fetch()
            # Save telemetry to database history
            db.save_telemetry(telemetry)
            # Wait exactly 1 second
            time.sleep(1.0)
        except Exception as e:
            print(f"Simulator Loop Error: {e}")
            time.sleep(1.0)

# Start background thread
sim_thread = threading.Thread(target=run_simulation_loop, daemon=True)
sim_thread.start()

# Mount API Routers
app.include_router(auth.router)
app.include_router(telemetry.router)
app.include_router(copilot.router)
app.include_router(predictive.router)
app.include_router(digital_twin.router)
app.include_router(executive.router)
app.include_router(approvals.router)
app.include_router(work_order.router)
app.include_router(maintenance.router)
app.include_router(audit.router)

# Mount system/static route last to prevent it from capturing API endpoints
app.include_router(system.router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
