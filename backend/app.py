import threading
import time
import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from simulator import simulator
from ai_model import ai_engine
from db import db
from predictive_model import predictive_model
from connectivity import DataAcquisitionService

# Initialize Start Time
start_time = time.time()

# Initialize FastAPI App
app = FastAPI(title="AetherTwin Backend Engine")

# Initialize DAQ Service
daq_service = DataAcquisitionService(simulator)

# Security & Header Protection Middleware (Task 39) with API versioning rewrite (Task 36)
@app.middleware("http")
async def security_hardening_middleware(request, call_next):
    path = request.scope.get("path", "")
    if path.startswith("/api/v1/"):
        request.scope["path"] = path.replace("/api/v1/", "/api/", 1)
        
    response = await call_next(request)
    
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Content-Security-Policy"] = "default-src 'self'"
    return response

# Configure CORS with security hardening (Task 39)
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

# --- Pydantic Data Models ---
class ControlSetpoints(BaseModel):
    pump_rpm: float | None = None
    valve_v101_open: float | None = None
    valve_v102_open: float | None = None
    drain_valve_open: float | None = None

class FaultTrigger(BaseModel):
    fault_type: str

class SettingsUpdate(BaseModel):
    normal_flow_setpoint: float | None = None
    max_pressure_threshold: float | None = None
    target_water_level: float | None = None

class DAQConfig(BaseModel):
    mode: str

class RESTTelemetry(BaseModel):
    telemetry: dict

class WhatIfRequest(BaseModel):
    scenario_type: str
    parameter_delta: float | None = None

class StrategySimulationRequest(BaseModel):
    fault_type: str

class FeedbackSubmission(BaseModel):
    prediction_id: str
    is_correct: bool
    correct_label: str | None = None
    notes: str | None = None

class ApprovalAction(BaseModel):
    approval_id: str
    action: str
    engineer: str
    notes: str | None = None

class WorkOrderRequest(BaseModel):
    component_id: str
    fault_type: str
    priority: str
    description: str

class LoginRequest(BaseModel):
    username: str
    password: str

# --- API Endpoints ---

@app.get("/")
def read_root():
    return {
        "status": "ONLINE",
        "service": "AetherTwin Industrial Intelligence API",
        "version": "1.0.0"
    }

@app.get("/health")
def health_check():
    # Observability & Health Check (Task 38)
    return {
        "status": "HEALTHY",
        "database_connected": db.use_mongo,
        "active_threads": threading.active_count()
    }

@app.get("/metrics")
def get_metrics():
    # Observability Metrics (Task 38)
    return {
        "uptime_seconds": round(time.time() - start_time, 1),
        "active_sessions": 1,
        "total_predictions_logged": len(db.get_audit_logs())
    }

@app.get("/api/telemetry/live")
def get_live_telemetry():
    # Retrieve latest step from DAQ
    telemetry = daq_service.fetch()
    # Run through AI evaluation
    ai_analysis = ai_engine.analyze_telemetry(telemetry)
    
    # Save prediction classification to audit logs (Task 29)
    classification = ai_analysis.get("classification", "NORMAL")
    db.save_audit_log(
        user="SYSTEM_AI",
        action="AI_PREDICTION",
        status="SUCCESS",
        details=f"Telemetry classified as {classification} with anomaly score {ai_analysis.get('anomaly_score', 0.0)}"
    )
    
    # If classification is critical (e.g. not NORMAL), auto-file a pending approval recommendation (Task 30)
    if classification != "NORMAL":
        pending = db.get_pending_approvals()
        if not any(a.get("recommendation", {}).get("fault_type") == classification for a in pending):
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

@app.get("/api/telemetry/history")
def get_history(limit: int = 50):
    return db.get_telemetry_history(limit)

@app.post("/api/controls")
def update_controls(controls: ControlSetpoints):
    daq_service.dispatch_control(
        pump_rpm=controls.pump_rpm,
        v101=controls.valve_v101_open,
        v102=controls.valve_v102_open,
        drain=controls.drain_valve_open
    )
    # Save action to audit logs (Task 29)
    db.save_audit_log(
        user="OPERATOR",
        action="CONTROL_SETPOINT_CHANGE",
        status="SUCCESS",
        details=f"Controls updated: RPM={controls.pump_rpm}, V101={controls.valve_v101_open}, V102={controls.valve_v102_open}"
    )
    return {"message": "Controls updated successfully", "current_state": daq_service.fetch()}

@app.post("/api/fault/trigger")
def trigger_fault(fault: FaultTrigger):
    success = simulator.trigger_fault(fault.fault_type)
    if not success:
        raise HTTPException(status_code=400, detail="Invalid fault type specified.")
    
    db.save_fault(fault.fault_type, f"Fault {fault.fault_type} triggered manually via dashboard.")
    return {"message": f"Fault {fault.fault_type} triggered successfully."}

@app.post("/api/fault/mitigate")
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

@app.get("/api/copilot/plan")
def get_copilot_plan():
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

@app.get("/api/settings")
def get_settings():
    return db.get_settings()

@app.post("/api/settings")
def update_settings(settings: SettingsUpdate):
    db.save_settings(settings.dict(exclude_unset=True))
    return {"message": "Settings updated successfully"}

@app.get("/api/azure/dtdl")
def get_dtdl():
    # Return the Digital Twins Definition Language (DTDL) version 2 for the plant components
    return [
        {
            "@id": "dtmi:ltts:aethertwin:WaterTreatmentPlant;1",
            "@type": "Interface",
            "displayName": "Industrial Water Treatment Plant Digital Twin",
            "@context": "dtmi:dtdl:context;2",
            "contents": [
                {
                    "@type": "Relationship",
                    "name": "hasSourceTank",
                    "target": "dtmi:ltts:aethertwin:StorageTank;1"
                },
                {
                    "@type": "Relationship",
                    "name": "hasBoosterPump",
                    "target": "dtmi:ltts:aethertwin:BoosterPump;1"
                },
                {
                    "@type": "Relationship",
                    "name": "hasSandFilter",
                    "target": "dtmi:ltts:aethertwin:SandFilter;1"
                },
                {
                    "@type": "Property",
                    "name": "healthStatus",
                    "schema": "string"
                }
            ]
        },
        {
            "@id": "dtmi:ltts:aethertwin:BoosterPump;1",
            "@type": "Interface",
            "displayName": "Booster Pump P-101 Model",
            "@context": "dtmi:dtdl:context;2",
            "contents": [
                {
                    "@type": "Telemetry",
                    "name": "vibration",
                    "schema": "double"
                },
                {
                    "@type": "Telemetry",
                    "name": "temperature",
                    "schema": "double"
                },
                {
                    "@type": "Telemetry",
                    "name": "rpm",
                    "schema": "double"
                },
                {
                    "@type": "Telemetry",
                    "name": "current",
                    "schema": "double"
                },
                {
                    "@type": "Property",
                    "name": "manufacturer",
                    "schema": "string",
                    "writable": False
                }
            ]
        },
        {
            "@id": "dtmi:ltts:aethertwin:StorageTank;1",
            "@type": "Interface",
            "displayName": "Storage Tank Model",
            "@context": "dtmi:dtdl:context;2",
            "contents": [
                {
                    "@type": "Telemetry",
                    "name": "level",
                    "schema": "double"
                },
                {
                    "@type": "Property",
                    "name": "capacityLiters",
                    "schema": "integer"
                }
            ]
        }
    ]

class ChatRequest(BaseModel):
    query: str

@app.post("/api/work-order/create")
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

@app.get("/api/assets")
def get_assets():
    return db.get_assets()

@app.post("/api/chat")
def post_chat(chat: ChatRequest):
    telemetry = daq_service.fetch()
    ai_analysis = ai_engine.analyze_telemetry(telemetry)
    live_data = {"telemetry": telemetry, "ai_analysis": ai_analysis}
    assets = db.get_assets()
    
    response = ai_engine.run_chat_query(chat.query, live_data, assets)
    return {"response": response}

@app.post("/api/alarm/acknowledge")
def acknowledge_alarm():
    simulator.alarm_acknowledged = True
    return {"message": "Alarm acknowledged successfully."}

@app.post("/api/auth/login")
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

@app.post("/api/alarm/escalate")
def escalate_alarm():
    active_fault = simulator.active_fault
    if active_fault == "NORMAL":
        return {"status": "SKIPPED", "message": "System is healthy. No alarm to escalate."}
        
    message = f"🚨 AETHERTWIN CRITICAL ALARM: {active_fault.replace('_', ' ')} has breached response SLA. Emergency shutdown sequence active. Please dispatch field crew immediately."
    res = ai_engine.send_sms_alert(message)
    
    # Save SMS notification log (Point 1)
    status_str = "Delivered" if res.get("status") != "error" else "Failed"
    dest_str = ai_engine.operator_phone or "Default Operator"
    db.save_notification("SMS", dest_str, message, status_str)
    
    # Simulate email broadcast to operations director
    email_msg = f"AetherTwin Industrial Critical Alert\n\nTarget Asset: {active_fault}\nStatus: SLA Breached (0s)\nAction: Immediate technical response dispatched."
    db.save_notification("Email", "operations-director@aethertwin.com", email_msg, "Sent")

    return {"status": "ESCALATED", "twilio_response": res}

@app.get("/api/faults/history")
def get_faults_history():
    return db.get_faults_history()

@app.get("/api/notifications/history")
def get_notifications_history():
    return db.get_notifications()

@app.get("/api/db/alarms")
def get_db_alarms():
    return db.get_db_alarms()

@app.get("/api/predictive/assets")
def get_predictive_assets():
    bearings = predictive_model.get_bearing_assets()
    assets = [{"asset_id": "Pump-101", "component_type": "Pump", "model_number": "Centrifugal-P101"}]
    assets.extend(bearings)
    return assets

@app.get("/api/predictive/high-risk")
def get_predictive_high_risk():
    return predictive_model.get_high_risk_assets()

@app.get("/api/predictive/predictions/{asset_id}")
def get_predictive_predictions(asset_id: str):
    live_fault = simulator.active_fault
    return predictive_model.get_predictions(asset_id, live_fault=live_fault)

@app.get("/api/predictive/telemetry/{asset_id}")
def get_predictive_telemetry(asset_id: str):
    return predictive_model.get_telemetry_history(asset_id)

@app.get("/api/predictive/maintenance/{asset_id}")
def get_predictive_maintenance(asset_id: str):
    return predictive_model.get_maintenance_history(asset_id)

@app.get("/api/executive/insights")
def get_executive_insights():
    # 1. Fetch live telemetry and run AI analysis to get active state
    telemetry = daq_service.fetch()
    ai_analysis = ai_engine.analyze_telemetry(telemetry)
    active_fault = simulator.active_fault
    
    # Calculate weighted plant health score
    if active_fault == "NORMAL":
        plant_health = 100.0
    elif active_fault == "PUMP_CAVITATION":
        plant_health = 65.0
    elif active_fault == "PIPE_LEAK":
        plant_health = 45.0
    elif active_fault == "VALVE_CLOG":
        plant_health = 80.0
    else:
        plant_health = 90.0
        
    pump_health_index = telemetry.get("pump_health_index", 100.0)
    if pump_health_index < plant_health:
        plant_health = pump_health_index

    # 2. Risk highlights
    high_risk_assets = []
    if active_fault != "NORMAL":
        high_risk_assets.append({
            "asset_id": "Pump-101",
            "component_type": "Booster Pump",
            "active_fault": active_fault,
            "risk_priority": ai_analysis.get("roi_calculator", {}).get("value_proposition", "High Risk"),
            "financial_risk_usd": ai_analysis.get("business_impact", {}).get("total_estimated_loss_usd", 0.0),
            "urgency": ai_analysis.get("maintenance_decision", {}).get("urgency_score", 0.0)
        })
        
    try:
        bearing_assets = predictive_model.get_bearing_assets()
        for b in bearing_assets:
            b_id = b.get("asset_id")
            preds = predictive_model.get_predictions(b_id, live_fault=active_fault)
            b_health = preds.get("health_index", 100.0)
            if b_health < 80.0:
                high_risk_assets.append({
                    "asset_id": b_id,
                    "component_type": "Bearing",
                    "active_fault": "BEARING_WEAR" if b_health < 60.0 else "PREVENTIVE_WARNING",
                    "risk_priority": "MEDIUM" if b_health >= 60.0 else "HIGH",
                    "financial_risk_usd": 535.0 if b_health < 60.0 else 85.0,
                    "urgency": round(100.0 - b_health, 1)
                })
    except Exception:
        pass
        
    # 3. Aggregate historical KPIs
    fault_history = db.get_faults_history()
    fault_count = len(fault_history)
    
    total_savings_usd = 4500.0 + (fault_count * 1250.0)
    total_downtime_avoided_hours = 16.5 + (fault_count * 4.5)
    total_energy_waste_saved_kwh = 120.0 + (fault_count * 35.0)
    mitigation_effectiveness_rate = 98.4
    
    # 4. Integrate current active values
    bi = ai_analysis.get("business_impact", {})
    roi = ai_analysis.get("roi_calculator", {})
    
    current_estimated_loss_usd = bi.get("total_estimated_loss_usd", 0.0)
    current_savings_usd = roi.get("maintenance_savings_usd", 0.0)
    current_downtime_avoided_hours = roi.get("downtime_avoided_hours", 0.0)
    
    return {
        "plant_health_score": round(plant_health, 1),
        "high_risk_assets": high_risk_assets,
        "kpis": {
            "total_downtime_avoided_hours": round(total_downtime_avoided_hours + current_downtime_avoided_hours, 1),
            "total_financial_savings_usd": round(total_savings_usd + current_savings_usd, 2),
            "total_energy_waste_saved_kwh": round(total_energy_waste_saved_kwh, 1),
            "mitigation_effectiveness_rate": mitigation_effectiveness_rate
        },
        "business_impact_summary": {
            "active_loss_exposure_usd": round(current_estimated_loss_usd, 2),
            "preventive_spend_usd": round(roi.get("planned_intervention_cost_usd", 0.0), 2),
            "net_roi_percentage": round(roi.get("roi_percentage", 0.0), 1),
            "value_proposition": roi.get("value_proposition", "System is running optimally.")
        }
    }

@app.get("/api/digital-twin/hierarchy")
def get_digital_twin_hierarchy(plant_id: str | None = None):
    # Support multiple factories & hierarchical asset organization (Task 27)
    plants = {
        "mumbai": {
            "plant_name": "Mumbai Industrial Water Plant A",
            "areas": [
                {
                    "area_id": "AREA-101",
                    "area_name": "Source & Pre-Treatment Area",
                    "lines": [
                        {
                            "line_id": "LINE-01",
                            "line_name": "Raw Inflow Supply Line 1",
                            "equipment": [
                                {"id": "V-101", "name": "Suction Side Control Valve (V-101)", "type": "Valve", "criticality": "HIGH"},
                                {"id": "P-101", "name": "High-Pressure Booster Pump (P-101)", "type": "Pump", "criticality": "CRITICAL"},
                                {"id": "P-102", "name": "Auxiliary Booster Pump (P-102)", "type": "Pump", "criticality": "MEDIUM"},
                                {"id": "F-101", "name": "Multi-Media Sand Filter (F-101)", "type": "Filter", "criticality": "HIGH"},
                                {"id": "V-102", "name": "Discharge Side Control Valve (V-102)", "type": "Valve", "criticality": "HIGH"}
                            ]
                        }
                    ]
                }
            ]
        },
        "chennai": {
            "plant_name": "Chennai Desalination Plant B",
            "areas": [
                {
                    "area_id": "AREA-201",
                    "area_name": "Intake & Screening Area",
                    "lines": [
                        {
                            "line_id": "LINE-02",
                            "line_name": "Seawater Intake Line 2",
                            "equipment": [
                                {"id": "P-201", "name": "Raw Seawater Intake Pump (P-201)", "type": "Pump", "criticality": "CRITICAL"},
                                {"id": "P-202", "name": "Auxiliary Intake Pump (P-202)", "type": "Pump", "criticality": "MEDIUM"}
                            ]
                        }
                    ]
                }
            ]
        },
        "delhi": {
            "plant_name": "Delhi Wastewater Treatment Plant C",
            "areas": [
                {
                    "area_id": "AREA-301",
                    "area_name": "Primary Clarification Area",
                    "lines": [
                        {
                            "line_id": "LINE-03",
                            "line_name": "Sludge Recycle Line 3",
                            "equipment": [
                                {"id": "P-301", "name": "Sludge Recycling Pump (P-301)", "type": "Pump", "criticality": "HIGH"},
                                {"id": "P-302", "name": "Auxiliary Sludge Pump (P-302)", "type": "Pump", "criticality": "MEDIUM"}
                            ]
                        }
                    ]
                }
            ]
        }
    }
    
    if plant_id and plant_id.lower() in plants:
        return plants[plant_id.lower()]
        
    return {
        "active_plant": plants["mumbai"],
        "all_registered_plants": [
            {"id": "mumbai", "name": "Mumbai Industrial Water Plant A"},
            {"id": "chennai", "name": "Chennai Desalination Plant B"},
            {"id": "delhi", "name": "Delhi Wastewater Treatment Plant C"}
        ]
    }

@app.get("/api/digital-twin/relationship-graph")
def get_digital_twin_relationship_graph():
    active_fault = simulator.active_fault
    
    propagation = {
        "active_fault": active_fault,
        "impact_severity": "NONE" if active_fault == "NORMAL" else "CRITICAL" if active_fault == "PIPE_LEAK" else "HIGH",
        "propagation_path": []
    }
    
    if active_fault == "PUMP_CAVITATION":
        propagation["propagation_path"] = [
            {"node": "V-101", "state": "BLOCKED", "role": "Origin", "description": "Suction flow restriction starving pump inlet."},
            {"node": "P-101", "state": "CAVITATING", "role": "Target", "description": "High vibration, thermal wear, bearing acceleration."},
            {"node": "F-101", "state": "LOW_PRESSURE", "role": "Downstream", "description": "Inflow drop to 1.7 L/min causing low bed filtration efficiency."}
        ]
    elif active_fault == "PIPE_LEAK":
        propagation["propagation_path"] = [
            {"node": "P-101", "state": "HIGH_FLOW", "role": "Origin", "description": "Pump running at full speed under low backpressure."},
            {"node": "Flange Seal F-101", "state": "RUPTURED", "role": "Target", "description": "Fluid escaping at weld seam, pressure dropped to 8 PSI."},
            {"node": "F-101", "state": "STARVED", "role": "Downstream", "description": "Discharge flow FIT-102 drops below 1.5 L/min; water levels failing."}
        ]
    elif active_fault == "VALVE_CLOG":
        propagation["propagation_path"] = [
            {"node": "F-101", "state": "CLOGGED", "role": "Origin", "description": "Sand media bed saturated with particulates."},
            {"node": "V-102", "state": "DEADHEADED", "role": "Target", "description": "Severe backpressure accumulation up to 58 PSI."},
            {"node": "P-101", "state": "OVERLOADED", "role": "Downstream", "description": "Motor current spikes to 7.2A, thermal casing winding warning."}
        ]
    
    return {
        "nodes": [
            {"id": "V-101", "label": "Suction Valve V-101", "status": "WARN" if active_fault == "PUMP_CAVITATION" else "OK"},
            {"id": "P-101", "label": "Booster Pump P-101", "status": "CRITICAL" if active_fault != "NORMAL" else "OK"},
            {"id": "F-101", "label": "Sand Filter F-101", "status": "WARN" if active_fault == "VALVE_CLOG" else "OK"},
            {"id": "V-102", "label": "Outlet Valve V-102", "status": "OK"}
        ],
        "edges": [
            {"source": "V-101", "target": "P-101", "relation": "Inflow Supply", "direction": "downstream"},
            {"source": "P-101", "target": "F-101", "relation": "Discharge Output", "direction": "downstream"},
            {"source": "F-101", "target": "V-102", "relation": "Filtration Output", "direction": "downstream"}
        ],
        "failure_propagation": propagation
    }

@app.get("/api/digital-twin/health-trajectory/{asset_id}")
def get_health_trajectory(asset_id: str):
    active_fault = simulator.active_fault
    telemetry = daq_service.fetch()
    pump_health = telemetry.get("pump_health_index", 100.0)
    
    history = []
    current_health = pump_health
    for i in range(10, 0, -1):
        past_health = min(100.0, current_health + (i * 0.1 if active_fault == "NORMAL" else i * 0.8))
        history.append({
            "step": -i,
            "health": round(past_health, 1),
            "state": "NORMAL" if past_health > 85.0 else "WARNING"
        })
    history.append({"step": 0, "health": round(pump_health, 1), "state": "NORMAL" if pump_health > 85.0 else "CRITICAL"})
    
    trajectory = []
    decay_rate = 0.05 if active_fault == "NORMAL" else 4.5 if active_fault == "PUMP_CAVITATION" else 7.5
    for i in range(1, 11):
        future_health = max(0.0, pump_health - (i * decay_rate))
        trajectory.append({
            "step": i,
            "predicted_health": round(future_health, 1),
            "state": "NORMAL" if future_health > 85.0 else "WARNING" if future_health > 50.0 else "CRITICAL"
        })
        
    return {
        "asset_id": asset_id,
        "current_health": round(pump_health, 1),
        "active_fault": active_fault,
        "degradation_history": history,
        "predicted_trajectory": trajectory,
        "time_to_critical_failure_hours": round(pump_health / decay_rate, 1) if active_fault != "NORMAL" else 720.0
    }

@app.get("/api/copilot/shift-report")
def get_shift_report():
    report_md = ai_engine.generate_shift_report()
    return {"report": report_md}

@app.get("/api/dashboards/{role}")
def get_role_dashboard(role: str):
    role = role.lower().strip()
    telemetry = daq_service.fetch()
    active_fault = simulator.active_fault
    ai_analysis = ai_engine.analyze_telemetry(telemetry)
    
    if role == "operator":
        return {
            "role": "Operator",
            "focus": "Real-time SCADA Monitoring & Fault Mitigation",
            "metrics": {
                "system_status": "NORMAL" if active_fault == "NORMAL" else "ALARM_TRIGGERED",
                "live_rpm": telemetry.get("pump_rpm", 0.0),
                "live_pressure": telemetry.get("pressure_pit101", 0.0),
                "live_vibration": telemetry.get("motor_vibration", 0.0)
            },
            "actions_allowed": ["mitigate_fault", "update_controls", "acknowledge_alarm"]
        }
    elif role == "maintenance":
        decision = ai_analysis.get("maintenance_decision", {})
        return {
            "role": "Maintenance Coordinator",
            "focus": "Technician Routing & Work Order Management",
            "metrics": {
                "active_work_orders_count": 1 if active_fault != "NORMAL" else 0,
                "suggested_technician": decision.get("personnel_skillset", "General Maintenance"),
                "required_spares": decision.get("required_spares", []),
                "urgency_score": decision.get("urgency_score", 0.0)
            },
            "actions_allowed": ["approve_work_order", "view_procedures", "order_spares"]
        }
    elif role == "reliability":
        return {
            "role": "Reliability Engineer",
            "focus": "Asset Degradation, RUL & Predictive Analytics",
            "metrics": {
                "pump_health_index": telemetry.get("pump_health_index", 100.0),
                "vibration_trend": telemetry.get("vibration_trend", "STABLE"),
                "estimated_rul_days": telemetry.get("pump_rul_hours", 720.0) / 24.0
            },
            "actions_allowed": ["view_health_trajectory", "retrain_models", "adjust_rules"]
        }
    elif role == "plant_manager":
        return {
            "role": "Plant Manager",
            "focus": "Operational Performance, Compliance & Audit Trail",
            "metrics": {
                "compliance_score": 100.0 if len(db.get_db_alarms()) == 0 else 94.5,
                "audit_logs_logged": len(db.get_audit_logs()),
                "total_alarms_this_week": len(db.get_db_alarms())
            },
            "actions_allowed": ["generate_shift_report", "view_audit_trail", "approve_mitigation"]
        }
    elif role == "executive":
        roi = ai_analysis.get("roi_calculator", {})
        return {
            "role": "Executive / Business Director",
            "focus": "ROI Analytics & Plant Financial Valuation",
            "metrics": {
                "maintenance_savings_usd": roi.get("maintenance_savings_usd", 0.0),
                "downtime_avoided_hours": roi.get("downtime_avoided_hours", 0.0),
                "energy_cost_saved_usd": roi.get("energy_cost_saved_usd", 0.0),
                "roi_percentage": roi.get("roi_percentage", 0.0)
            },
            "actions_allowed": ["view_executive_summary", "export_financials"]
        }
    else:
        raise HTTPException(status_code=400, detail="Invalid role specified. Supported roles: operator, maintenance, reliability, plant_manager, executive.")

@app.get("/api/audit/logs")
def get_audit_trail():
    return db.get_audit_logs()

@app.get("/api/approvals/pending")
def get_pending_approvals():
    return db.get_pending_approvals()

@app.post("/api/approvals/action")
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

@app.get("/api/predictive/risk-score/{asset_id}")
def get_asset_risk_score(asset_id: str):
    return ai_engine.calculate_predictive_risk_score(asset_id)

@app.get("/api/intelligence/multi-agent")
def get_multi_agent_consensus():
    telemetry = daq_service.fetch()
    ai_analysis = ai_engine.analyze_telemetry(telemetry)
    rule_events = ai_analysis.get("rule_events", [])
    res = ai_engine.run_multi_agent_consensus(telemetry, rule_events)
    return res

@app.get("/api/intelligence/knowledge-graph")
def get_knowledge_graph():
    return ai_engine.get_root_cause_knowledge_graph()

@app.post("/api/digital-twin/what-if")
def post_what_if(req: WhatIfRequest):
    return ai_engine.simulate_what_if_scenario(
        scenario_type=req.scenario_type,
        parameter_delta=req.parameter_delta
    )

@app.post("/api/maintenance/simulate-strategies")
def post_simulate_strategies(req: StrategySimulationRequest):
    return ai_engine.simulate_maintenance_strategies(fault_type=req.fault_type)

@app.post("/api/feedback/submit")
def submit_feedback(fb: FeedbackSubmission):
    db.save_feedback(
        prediction_id=fb.prediction_id,
        is_correct=fb.is_correct,
        correct_label=fb.correct_label,
        notes=fb.notes
    )
    return {"message": "Feedback submitted successfully."}

@app.post("/api/feedback/retrain")
def trigger_retraining():
    res = ai_engine.retrain_models()
    if res.get("status") == "error":
        raise HTTPException(status_code=500, detail=res.get("message"))
    return res

@app.get("/api/feedback/models")
def get_models_registry():
    reg_path = os.path.join(os.path.dirname(__file__), "models_registry.json")
    if not os.path.exists(reg_path):
        raise HTTPException(status_code=404, detail="Models registry not found.")
    import json
    try:
        with open(reg_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/daq/config")
def get_daq_config():
    return {"mode": daq_service.mode}

@app.post("/api/daq/config")
def post_daq_config(config: DAQConfig):
    success = daq_service.set_mode(config.mode)
    if not success:
        raise HTTPException(status_code=400, detail="Invalid DAQ mode specified.")
    return {"message": f"DAQ mode updated to {config.mode}"}

@app.post("/api/daq/input")
def post_daq_input(data: RESTTelemetry):
    daq_service.ingest_rest_telemetry(data.telemetry)
    return {"message": "Telemetry successfully ingested via REST."}

# Serve compiled Angular static files in production mode
current_dir = os.path.dirname(os.path.abspath(__file__))
frontend_dist = os.path.abspath(os.path.join(current_dir, "..", "frontend", "dist", "frontend", "browser"))

if os.path.exists(frontend_dist):
    @app.get("/{path_name:path}")
    def serve_frontend(path_name: str):
        # Prevent intercepting API routes
        if path_name.startswith("api/"):
            raise HTTPException(status_code=404, detail="API route not found")
            
        # Check if file exists in Angular build output
        file_path = os.path.join(frontend_dist, path_name)
        if os.path.exists(file_path) and os.path.isfile(file_path):
            return FileResponse(file_path)
            
        # Fallback to index.html for Single Page Application client routing
        index_path = os.path.join(frontend_dist, "index.html")
        if os.path.exists(index_path):
            return FileResponse(index_path)
            
        raise HTTPException(status_code=404, detail="Static index.html not found")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)
