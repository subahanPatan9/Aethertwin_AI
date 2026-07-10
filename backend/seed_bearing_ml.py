import os
import random
from datetime import datetime, timedelta
from pymongo import MongoClient

def seed_database():
    mongo_uri = os.environ.get("MONGO_URI", "mongodb://localhost:27017/")
    print(f"Connecting to MongoDB at {mongo_uri}...")
    
    client = MongoClient(mongo_uri, serverSelectionTimeoutMS=2000)
    try:
        client.admin.command('ping')
    except Exception as e:
        print(f"Error: Could not connect to MongoDB: {e}")
        return

    # Use a separate database as requested
    db = client["bearing_predictive_maintenance"]
    print("Successfully connected. Seeding database 'bearing_predictive_maintenance'...")

    # Drop existing collections to clean start
    db["assets"].drop()
    db["telemetry_vibration"].drop()
    db["operational_context"].drop()
    db["maintenance_events"].drop()
    db["ml_predictions"].drop()

    # 1. Seed assets (100 documents)
    print("Generating 100 assets...")
    assets_docs = []
    bearing_models = ["SKF-6205-2RSH", "FAG-6306-2Z", "NSK-6204-ZZ", "NTN-6308"]
    for i in range(1, 101):
        asset_id = f"BRG-{i:03d}"
        assets_docs.append({
          "asset_id": asset_id,
          "component_type": "Bearing",
          "model_number": random.choice(bearing_models),
          "installation_date": datetime.utcnow() - timedelta(days=random.randint(30, 365)),
          "defect_frequencies_hz": {
            "bpfo": round(random.uniform(3.0, 4.5), 2),
            "bpfi": round(random.uniform(5.0, 6.5), 2),
            "bsf":  round(random.uniform(2.0, 3.0), 2),
            "ftf":  round(random.uniform(0.3, 0.5), 2)
          },
          "operational_limits": {
            "max_rpm": random.choice([1800, 3600]),
            "vibration_threshold_rms_g": round(random.uniform(2.0, 3.5), 1),
            "critical_temp_c": round(random.uniform(80.0, 95.0), 1)
          }
        })
    db["assets"].insert_many(assets_docs)

    # Generating unique data profiles for all 100 assets
    print("Generating telemetry, context, and predictions for all 100 assets...")
    vibration_docs = []
    context_docs = []
    predictions_docs = []
    
    base_time = datetime.utcnow() - timedelta(days=100)
    
    for i in range(1, 101):
        asset_id = f"BRG-{i:03d}"
        
        # Each asset gets a unique wear profile
        degradation_speed = random.uniform(0.65, 1.35)
        start_vibration = random.uniform(0.35, 0.95)
        max_vibration = random.uniform(2.1, 3.3)
        
        for day in range(100):
            timestamp = base_time + timedelta(days=day)
            progress = day / 100.0
            
            # Telemetry Vibration
            degradation_factor = (progress ** 2) * degradation_speed
            base_rms = start_vibration + degradation_factor * (max_vibration - start_vibration)
            accel_rms = round(base_rms + random.uniform(-0.08, 0.08), 3)
            accel_peak = round(accel_rms * random.uniform(1.8, 2.8), 3)
            kurtosis = round(3.0 + degradation_factor * 2.2 + random.uniform(-0.15, 0.15), 2)
            crest_factor = round(accel_peak / accel_rms, 2)
            
            vibration_docs.append({
              "timestamp": timestamp,
              "asset_id": asset_id,
              "time_domain": {
                "accel_rms": accel_rms,
                "accel_peak": accel_peak,
                "kurtosis": kurtosis,
                "crest_factor": crest_factor,
                "skewness": round(random.uniform(-0.25, 0.25), 3)
              },
              "frequency_domain": {
                "spectral_entropy": round(random.uniform(0.45, 0.75), 2),
                "outer_race_energy": round(degradation_factor * 1.2 + random.uniform(0.05, 0.12), 3),
                "inner_race_energy": round(random.uniform(0.05, 0.12), 3)
              }
            })
            
            # Operational Context
            context_docs.append({
              "timestamp": timestamp,
              "asset_id": asset_id,
              "rpm": round(1495 + random.uniform(-8, 8), 1),
              "load_percentage": round(75.0 + random.uniform(-4.0, 8.0), 1),
              "temperature_c": round(42.0 + degradation_factor * 22.0 + random.uniform(-1.5, 1.5), 1),
              "motor_current_amps": round(12.5 + random.uniform(-0.4, 0.6), 2)
            })
            
            # ML Predictions
            p_7d = round((progress ** 3) * 0.95 * degradation_speed, 2)
            p_14d = round((progress ** 2) * 0.98 * degradation_speed, 2)
            p_30d = round(progress * 0.99 * degradation_speed, 2)
            
            p_7d = min(1.0, max(0.0, p_7d))
            p_14d = min(1.0, max(0.0, p_14d))
            p_30d = min(1.0, max(0.0, p_30d))
            
            status = "NORMAL"
            action = "Continuous telemetry monitoring."
            if p_30d > 0.70:
                status = "CRITICAL"
                action = "Schedule bearing overhaul replacement immediately."
            elif p_30d > 0.40:
                status = "WARNING"
                action = "Schedule inspection and greasing within next 5 days."
                
            predictions_docs.append({
              "timestamp": timestamp,
              "asset_id": asset_id,
              "current_vibration_status": status,
              "failure_probabilities": {
                "within_7_days": p_7d,
                "within_14_days": p_14d,
                "within_30_days": p_30d
              },
              "recommended_action": action,
              "confidence_score": round(0.85 + random.uniform(0.01, 0.10), 2)
            })

    print("Inserting telemetry_vibration...")
    db["telemetry_vibration"].insert_many(vibration_docs)
    print("Inserting operational_context...")
    db["operational_context"].insert_many(context_docs)
    
    # Generate 100 maintenance logs tied randomly to all 100 assets
    print("Generating 100 maintenance logs...")
    maintenance_docs = []
    event_types = ["LUBRICATION", "INSPECTION", "PREVENTIVE_REPLACEMENT", "FAILURE"]
    component_parts = ["Outer Race", "Inner Race", "Ball Cage", "Seal"]
    for i in range(1, 101):
        timestamp = datetime.utcnow() - timedelta(days=random.randint(1, 730))
        event_type = random.choices(event_types, weights=[50, 35, 10, 5], k=1)[0]
        notes = ""
        technician_action = ""
        failure_type = "None"
        if event_type == "LUBRICATION":
            notes = "Routine greasing of bearing housing."
            technician_action = "Applied Mobilith SHC 100 grease."
        elif event_type == "INSPECTION":
            notes = "Visual and audio checks completed."
            technician_action = "Inspected seals. Normal audio signature."
        elif event_type == "PREVENTIVE_REPLACEMENT":
            notes = "Scheduled overhaul replacement based on running hours."
            technician_action = "Replaced with new SKF bearing."
        else:
            notes = "Sudden breakdown due to severe outer/inner race surface spalling."
            technician_action = "Performed emergency replacement."
            failure_type = random.choice(component_parts)
            
        maintenance_docs.append({
          "event_id": f"EVT-{i:03d}",
          "asset_id": f"BRG-{random.randint(1, 100):03d}",
          "event_type": event_type,
          "timestamp": timestamp,
          "failure_type": failure_type,
          "notes": notes,
          "technician_action": technician_action
        })
    db["maintenance_events"].insert_many(maintenance_docs)
    
    print("Inserting ml_predictions...")
    db["ml_predictions"].insert_many(predictions_docs)

    print("\n--- Seeding Complete ---")
    print(f"Collections seeded in database 'bearing_predictive_maintenance':")
    for name in ["assets", "telemetry_vibration", "operational_context", "maintenance_events", "ml_predictions"]:
        print(f" - {name}: {db[name].count_documents({})} documents")

if __name__ == "__main__":
    seed_database()
