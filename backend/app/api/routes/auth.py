import os
from fastapi import APIRouter, HTTPException
from app.schemas.validation import LoginRequest

router = APIRouter(prefix="/api/auth", tags=["auth"])

@router.post("/login")
def login(creds: LoginRequest):
    username = creds.username.lower().strip() if creds.username else ""
    password = creds.password.strip() if creds.password else ""
    
    env_username = os.environ.get("DEVOPS_USERNAME", "goh0972.hyd016@hackathonindia.net").lower().strip()
    env_password = os.environ.get("DEVOPS_PASSWORD", "HYD@40*065").strip()
    
    # Lead Engineer Credentials
    if username == env_username and password == env_password:
        return {
            "status": "SUCCESS",
            "role": "ENGINEER",
            "username": env_username,
            "name": "Lead Control Engineer"
        }
    # Backup Engineer Credentials
    elif username == "engineer" and password == "admin123":
        return {
            "status": "SUCCESS",
            "role": "ENGINEER",
            "username": "engineer",
            "name": "Field Maintenance Engineer"
        }
    # Operator Role
    elif (username == "operator" or username == "guest") and (password == "operator123" or password == ""):
        return {
            "status": "SUCCESS",
            "role": "OPERATOR",
            "username": "operator",
            "name": "SCADA Console Operator"
        }
    else:
        raise HTTPException(status_code=401, detail="Invalid credentials. Access Denied.")
