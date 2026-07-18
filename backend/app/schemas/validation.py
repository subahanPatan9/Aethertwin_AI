from pydantic import BaseModel

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

class ChatRequest(BaseModel):
    query: str
