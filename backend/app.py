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

# Initialize FastAPI App
app = FastAPI(title="AetherTwin Backend Engine")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For demo simplicity, allow all. In prod, restrict.
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Background Simulator Thread
def run_simulation_loop():
    print("Simulator: Background physical thread started.")
    while True:
        try:
            # Step the simulation forward
            telemetry = simulator.update()
            
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

@app.get("/api/telemetry/live")
def get_live_telemetry():
    # Retrieve latest step from simulator
    telemetry = simulator.update()
    # Run through AI evaluation
    ai_analysis = ai_engine.analyze_telemetry(telemetry)
    
    return {
        "telemetry": telemetry,
        "ai_analysis": ai_analysis
    }

@app.get("/api/telemetry/history")
def get_history(limit: int = 50):
    return db.get_telemetry_history(limit)

@app.post("/api/controls")
def update_controls(controls: ControlSetpoints):
    simulator.set_controls(
        pump_rpm=controls.pump_rpm,
        v101=controls.valve_v101_open,
        v102=controls.valve_v102_open,
        drain=controls.drain_valve_open
    )
    return {"message": "Controls updated successfully", "current_state": simulator.update()}

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
        
    # Apply changes to simulator to physically resolve the safety hazard
    if active_fault == "PUMP_CAVITATION":
        # Shutdown pump and open inlet valve fully
        simulator.set_controls(pump_rpm=0, v101=100)
    elif active_fault == "PIPE_LEAK":
        # Shutdown pump and isolate both valves
        simulator.set_controls(pump_rpm=0, v101=0, v102=0)
    elif active_fault == "VALVE_CLOG":
        # Shutdown pump and open outlet valve fully to try to relief
        simulator.set_controls(pump_rpm=0, v102=100)
        
    # Reset fault state to Normal
    simulator.trigger_fault("NORMAL")
    db.clear_faults()
    
    return {
        "message": f"AI safety mitigation applied successfully for {active_fault}. System interlocks tripped.",
        "new_state": simulator.update()
    }

@app.get("/api/copilot/plan")
def get_copilot_plan():
    active_fault = simulator.active_fault
    telemetry = simulator.update()
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
    telemetry = simulator.update()
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
