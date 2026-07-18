from fastapi import APIRouter
from app.repositories.db_repo import db
from app.schemas.validation import ApprovalAction

router = APIRouter(prefix="/api/approvals", tags=["approvals"])

@router.get("/pending")
def get_pending_approvals():
    return db.get_pending_approvals()

@router.post("/action")
def apply_approval_action(act: ApprovalAction):
    db.action_approval(
        approval_id=act.approval_id,
        action=act.action,
        engineer=act.engineer,
        notes=act.notes
    )
    db.save_audit_log(
        user=act.engineer,
        action=f"RECOMMENDATION_{act.action}",
        status="SUCCESS",
        details=f"Engineer {act.engineer} {act.action.lower()} recommendation {act.approval_id}. Notes: {act.notes}"
    )
    return {"message": f"Approval {act.approval_id} processed as {act.action}."}
