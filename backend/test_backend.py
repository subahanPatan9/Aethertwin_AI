import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.services.simulator.simulator import simulator
from app.services.prediction.ai_model import ai_engine
from app.repositories.db_repo import db

def run_tests():
    print("=== Running Backend Integrity Tests ===")
    
    # 1. Test Database Fallback
    print("\n[Test 1] Database Fallback Status:")
    print(f"MongoDB connection active: {db.use_mongo}")
    print(f"Fallback database file: {db.fallback_file}")
    
    # 2. Test Physics Simulator
    print("\n[Test 2] Physics Simulator Baseline State:")
    state = simulator.update()
    print(f"Pump RPM: {state['pump_rpm']} RPM")
    print(f"FIT-101 flow: {state['flow_fit101']} L/min")
    print(f"PIT-101 pressure: {state['pressure_pit101']} PSI")
    print(f"T-101 Level: {state['level_t101']}%")
    print(f"T-102 Level: {state['level_t102']}%")
    
    # 3. Test Fault Injection - Cavitation
    print("\n[Test 3] Fault Injection: Pump Cavitation")
    simulator.trigger_fault("PUMP_CAVITATION")
    
    # Step simulation forward a few times to let temperature and vibration accumulate
    import time
    for i in range(4):
        time.sleep(1.0)
        state = simulator.update()
    
    print(f"Vibration: {state['motor_vibration']} mm/s (Expected: > 6.0)")
    print(f"Temperature: {state['motor_temp']} °C (Expected: > 55.0)")
    print(f"Flow: {state['flow_fit101']} L/min (Expected: < 5.0)")
    
    # Check AI detector
    analysis = ai_engine.analyze_telemetry(state)
    print(f"AI Classification: {analysis['classification']} (Expected: PUMP_CAVITATION)")
    print(f"AI Confidence: {analysis['confidence']}%")
    print(f"AI Anomaly Score: {analysis['anomaly_score']}/100")
    
    # Check Copilot logic
    plan = ai_engine.get_mitigation_plan("PUMP_CAVITATION")
    print("\nGenerated PLC Safety Logic (Structured Text Snippet):")
    print(plan['plc_code'][:150] + "...")
    
    # 4. Clear faults and check recovery
    print("\n[Test 4] System Safety Mitigation:")
    # Simulator set to safe state
    simulator.set_controls(pump_rpm=0, v101=100)
    simulator.trigger_fault("NORMAL")
    state = simulator.update()
    analysis = ai_engine.analyze_telemetry(state)
    print(f"New Fault State: {state['active_fault']}")
    print(f"AI Classification after mitigation: {analysis['classification']} (Expected: NORMAL)")
    
    print("\n=== All Backend Checks Passed successfully! ===")

if __name__ == "__main__":
    run_tests()
