from fastapi import APIRouter
from app.repositories.db_repo import db
from app.services.simulator.simulator import simulator
from app.services.prediction.predictive_model import predictive_model
from app.services.prediction.ai_model import ai_engine

router = APIRouter(prefix="/api", tags=["predictive"])

@router.get("/assets")
def get_assets():
    return db.get_assets()

@router.get("/predictive/assets")
def get_predictive_assets():
    bearings = predictive_model.get_bearing_assets()
    assets = [{"asset_id": "Pump-101", "component_type": "Pump", "model_number": "Centrifugal-P101"}]
    assets.extend(bearings)
    return assets

@router.get("/predictive/high-risk")
def get_predictive_high_risk():
    return predictive_model.get_high_risk_assets()

@router.get("/predictive/predictions/{asset_id}")
def get_predictive_predictions(asset_id: str):
    live_fault = simulator.active_fault
    return predictive_model.get_predictions(asset_id, live_fault=live_fault)

@router.get("/predictive/telemetry/{asset_id}")
def get_predictive_telemetry(asset_id: str):
    return predictive_model.get_telemetry_history(asset_id)

@router.get("/predictive/maintenance/{asset_id}")
def get_predictive_maintenance(asset_id: str):
    return predictive_model.get_maintenance_history(asset_id)

@router.get("/predictive/risk-score/{asset_id}")
def get_asset_risk_score(asset_id: str):
    return ai_engine.calculate_predictive_risk_score(asset_id)
