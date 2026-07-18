import time
from fastapi import APIRouter
from app.repositories.db_repo import db
from app.services.prediction.ai_model import ai_engine
from app.schemas.validation import WorkOrderRequest

router = APIRouter(prefix="/api/work-order", tags=["work-order"])

@router.post("/create")
def create_work_order(wo: WorkOrderRequest):
    # Update active fault status to "In Progress"
    db.update_fault_status(wo.fault_type, "In Progress")
    
    # Save notification log
    db.save_notification("DevOps Ticket", wo.component_id, f"Azure DevOps maintenance work item created for active fault: {wo.fault_type}", "Dispatched")

    # Try to create real DevOps work item first
    real_ticket = ai_engine.create_azure_devops_workitem(
        component_id=wo.component_id,
        fault_type=wo.fault_type,
        priority=wo.priority,
        description=wo.description
    )
    
    if real_ticket:
        return {
            "status": "CREATED",
            "ticket_id": real_ticket["ticket_id"],
            "timestamp": time.time(),
            "azure_devops_url": real_ticket["url"],
            "message": f"Azure DevOps task {real_ticket['ticket_id']} successfully created and synced to cloud board."
        }
        
    # Mock fallback
    ticket_id = f"WO-{int(time.time()) % 1000000:06d}"
    return {
        "status": "CREATED",
        "ticket_id": ticket_id,
        "timestamp": time.time(),
        "azure_devops_url": f"https://dev.azure.com/ltts-hackathon/AetherTwin/_workitems/edit/{ticket_id}",
        "message": f"Azure DevOps maintenance ticket {ticket_id} created in offline mock mode (DevOps credentials missing)."
    }
