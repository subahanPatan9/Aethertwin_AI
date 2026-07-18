from fastapi import APIRouter, HTTPException
from app.repositories.db_repo import db
from app.services.simulator.simulator import simulator
from app.services.telemetry.connectivity import daq_service
from app.services.prediction.ai_model import ai_engine
from app.schemas.validation import ControlSetpoints, FaultTrigger, SettingsUpdate, DAQConfig, RESTTelemetry

router = APIRouter(prefix="/api", tags=["telemetry"])

@router.get("/telemetry/live")
def get_live_telemetry():
    # Retrieve latest step from DAQ
    telemetry = daq_service.fetch()
    # Run through AI evaluation
    ai_analysis = ai_engine.analyze_telemetry(telemetry)
    
    # Save prediction classification to audit logs
    classification = ai_analysis.get("classification", "NORMAL")
    db.save_audit_log(
        user="SYSTEM_AI",
        action="AI_PREDICTION",
        status="SUCCESS",
        details=f"Telemetry classified as {classification} with anomaly score {ai_analysis.get('anomaly_score', 0.0)}"
    )
    
    # If classification is critical (e.g. not NORMAL), auto-file a pending approval recommendation
    if classification != "NORMAL":
        pending = db.get_pending_approvals()
        if not any(isinstance(a, dict) and isinstance(a.get("recommendation"), dict) and a.get("recommendation", {}).get("fault_type") == classification for a in pending):
            import uuid
            approval_id = f"APP-{uuid.uuid4().hex[:6].upper()}"
            db.save_approval(
                approval_id=approval_id,
                recommendation={
                    "fault_type": classification,
                    "actions": ai_analysis.get("maintenance_decision", {}).get("suggested_procedures", [])
                },
                priority="HIGH"
            )
            
    return {
        "telemetry": telemetry,
        "ai_analysis": ai_analysis
    }

@router.get("/telemetry/history")
def get_history(limit: int = 50):
    return db.get_telemetry_history(limit)

@router.post("/controls")
def update_controls(controls: ControlSetpoints):
    daq_service.dispatch_control(
        pump_rpm=controls.pump_rpm,
        v101=controls.valve_v101_open,
        v102=controls.valve_v102_open,
        drain=controls.drain_valve_open
    )
    # Save action to audit logs
    db.save_audit_log(
        user="OPERATOR",
        action="CONTROL_SETPOINT_CHANGE",
        status="SUCCESS",
        details=f"Controls updated: RPM={controls.pump_rpm}, V101={controls.valve_v101_open}, V102={controls.valve_v102_open}"
    )
    return {"message": "Controls updated successfully", "current_state": daq_service.fetch()}

@router.post("/fault/trigger")
def trigger_fault(fault: FaultTrigger):
    success = simulator.trigger_fault(fault.fault_type)
    if not success:
        raise HTTPException(status_code=400, detail="Invalid fault type specified.")
    
    db.save_fault(fault.fault_type, f"Fault {fault.fault_type} triggered manually via dashboard.")
    return {"message": f"Fault {fault.fault_type} triggered successfully."}

@router.post("/fault/mitigate")
def apply_mitigation():
    active_fault = simulator.active_fault
    if active_fault == "NORMAL":
        return {"message": "System is already running normally."}
        
    # Apply changes to physical loop via DAQ to resolve the safety hazard
    if active_fault == "PUMP_CAVITATION":
        daq_service.dispatch_control(pump_rpm=0, v101=100)
    elif active_fault == "PIPE_LEAK":
        daq_service.dispatch_control(pump_rpm=0, v101=0, v102=0)
    elif active_fault == "VALVE_CLOG":
        daq_service.dispatch_control(pump_rpm=0, v102=100)
        
    # Reset fault state to Normal
    simulator.trigger_fault("NORMAL")
    db.clear_faults()
    
    return {
        "message": f"AI safety mitigation applied successfully for {active_fault}. System interlocks tripped.",
        "new_state": daq_service.fetch()
    }

@router.post("/alarm/acknowledge")
def acknowledge_alarm():
    simulator.alarm_acknowledged = True
    return {"message": "Alarm acknowledged successfully."}

@router.post("/alarm/escalate")
def escalate_alarm():
    active_fault = simulator.active_fault
    if active_fault == "NORMAL":
        return {"status": "SKIPPED", "message": "System is healthy. No alarm to escalate."}
        
    message = f"🚨 AETHERTWIN CRITICAL ALARM: {active_fault.replace('_', ' ')} has breached response SLA. Emergency shutdown sequence active. Please dispatch field crew immediately."
    res = ai_engine.send_sms_alert(message)
    
    # Save SMS notification log
    status_str = "Delivered" if res.get("status") != "error" else "Failed"
    dest_str = ai_engine.operator_phone or "Default Operator"
    db.save_notification("SMS", dest_str, message, status_str)
    
    # Simulate email broadcast to operations director
    email_msg = f"AetherTwin Industrial Critical Alert\n\nTarget Asset: {active_fault}\nStatus: SLA Breached (0s)\nAction: Dispatched immediate response."
    db.save_notification("Email", "operations-director@aethertwin.com", email_msg, "Sent")

    return {"status": "ESCALATED", "twilio_response": res}

@router.get("/daq/config")
def get_daq_config():
    return {"mode": daq_service.mode}

@router.post("/daq/config")
def post_daq_config(config: DAQConfig):
    success = daq_service.set_mode(config.mode)
    if not success:
        raise HTTPException(status_code=400, detail="Invalid DAQ mode specified.")
    return {"message": f"DAQ mode updated to {config.mode}"}

@router.post("/daq/input")
def post_daq_input(data: RESTTelemetry):
    daq_service.ingest_rest_telemetry(data.telemetry)
    return {"message": "Telemetry successfully ingested via REST."}

@router.get("/settings")
def get_settings():
    return db.get_settings()

@router.post("/settings")
def update_settings(settings: SettingsUpdate):
    db.save_settings(settings.dict(exclude_unset=True))
    return {"message": "Settings updated successfully"}
