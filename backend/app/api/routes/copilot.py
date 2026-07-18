import os
import json
from fastapi import APIRouter, HTTPException
from app.core import config
from app.repositories.db_repo import db
from app.services.telemetry.connectivity import daq_service
from app.services.prediction.ai_model import ai_engine
from app.schemas.validation import ChatRequest, FeedbackSubmission

router = APIRouter(prefix="/api", tags=["copilot"])

@router.get("/copilot/plan")
def get_copilot_plan():
    # Avoid dynamic relative imports
    from app.services.simulator.simulator import simulator
    active_fault = simulator.active_fault
    telemetry = daq_service.fetch()
    plan = ai_engine.generate_llm_diagnostics(active_fault, telemetry)
    return {
        "fault_type": active_fault,
        "rca": plan["rca"],
        "mitigation": plan["mitigation"],
        "plc_code": plan["plc_code"],
        "dtdl_patch": plan["dtdl_patch"]
    }

@router.get("/copilot/shift-report")
def get_shift_report():
    report_md = ai_engine.generate_shift_report()
    return {"report": report_md}

@router.post("/chat")
def post_chat(chat: ChatRequest):
    telemetry = daq_service.fetch()
    ai_analysis = ai_engine.analyze_telemetry(telemetry)
    live_data = {"telemetry": telemetry, "ai_analysis": ai_analysis}
    assets = db.get_assets()
    
    response = ai_engine.run_chat_query(chat.query, live_data, assets)
    return {"response": response}

@router.post("/feedback/submit")
def submit_feedback(fb: FeedbackSubmission):
    db.save_feedback(
        prediction_id=fb.prediction_id,
        is_correct=fb.is_correct,
        correct_label=fb.correct_label,
        notes=fb.notes
    )
    return {"message": "Feedback submitted successfully."}

@router.post("/feedback/retrain")
def trigger_retraining():
    res = ai_engine.retrain_models()
    if res.get("status") == "error":
        raise HTTPException(status_code=500, detail=res.get("message"))
    return res

@router.get("/feedback/models")
def get_models_registry():
    reg_path = os.path.join(config.BASE_DIR, "models_registry.json")
    if not os.path.exists(reg_path):
        raise HTTPException(status_code=404, detail="Models registry not found.")
    try:
        with open(reg_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
