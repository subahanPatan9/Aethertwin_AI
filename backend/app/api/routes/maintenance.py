from fastapi import APIRouter
from app.services.prediction.ai_model import ai_engine
from app.schemas.validation import StrategySimulationRequest

router = APIRouter(prefix="/api/maintenance", tags=["maintenance"])

@router.post("/simulate-strategies")
def post_simulate_strategies(req: StrategySimulationRequest):
    return ai_engine.simulate_maintenance_strategies(fault_type=req.fault_type)
