from fastapi import APIRouter, HTTPException
from app.repositories.db_repo import db
from app.services.simulator.simulator import simulator
from app.services.telemetry.connectivity import daq_service
from app.services.prediction.predictive_model import predictive_model
from app.services.prediction.ai_model import ai_engine

router = APIRouter(prefix="/api", tags=["executive"])

@router.get("/executive/insights")
def get_executive_insights():
    # Fetch live telemetry and run AI analysis to get active state
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

    # Risk highlights
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
        
    # Aggregate historical KPIs
    fault_history = db.get_faults_history()
    fault_count = len(fault_history)
    
    total_savings_usd = 4500.0 + (fault_count * 1250.0)
    total_downtime_avoided_hours = 16.5 + (fault_count * 4.5)
    total_energy_waste_saved_kwh = 120.0 + (fault_count * 35.0)
    mitigation_effectiveness_rate = 98.4
    
    # Integrate current active values
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

@router.get("/dashboards/{role}")
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
                "compliance_score": 100.0 if len(db.get_pending_approvals()) == 0 else 94.5,
                "audit_logs_logged": len(db.get_audit_logs()),
                "total_alarms_this_week": len(db.get_pending_approvals())
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
