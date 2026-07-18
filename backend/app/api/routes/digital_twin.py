from fastapi import APIRouter
from app.services.simulator.simulator import simulator
from app.services.telemetry.connectivity import daq_service
from app.services.prediction.ai_model import ai_engine
from app.schemas.validation import WhatIfRequest

router = APIRouter(prefix="/api", tags=["digital_twin"])

@router.get("/digital-twin/hierarchy")
def get_digital_twin_hierarchy(plant_id: str | None = None):
    # Support multiple factories & hierarchical asset organization
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

@router.get("/digital-twin/relationship-graph")
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

@router.get("/digital-twin/health-trajectory/{asset_id}")
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

@router.post("/digital-twin/what-if")
def post_what_if(req: WhatIfRequest):
    return ai_engine.simulate_what_if_scenario(
        scenario_type=req.scenario_type,
        parameter_delta=req.parameter_delta
    )

@router.get("/azure/dtdl")
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
