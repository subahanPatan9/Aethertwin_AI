import json
import os
from datetime import datetime
import threading
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError

class Database:
    def __init__(self):
        self.use_mongo = False
        self.client = None
        self.db = None
        self.lock = threading.Lock()
        self.fallback_file = os.path.join(os.path.dirname(__file__), "db_fallback.json")
        
        # Initialize default fallback structure if file does not exist
        if not os.path.exists(self.fallback_file):
            self._write_fallback({
                "telemetry": [],
                "faults": [],
                "settings": {
                    "normal_flow_setpoint": 15.0,
                    "max_pressure_threshold": 45.0,
                    "target_water_level": 80.0
                }
            })

        # Try connecting to local MongoDB
        try:
            # Check environment variable first (for Docker container link)
            mongo_uri = os.environ.get("MONGO_URI", "mongodb://localhost:27017/")
            # 1.5s timeout so startup is fast even if MongoDB is not running
            self.client = MongoClient(mongo_uri, serverSelectionTimeoutMS=1500)
            # Force connection check
            self.client.admin.command('ping')
            self.db = self.client["aethertwin"]
            self.use_mongo = True
            print("Successfully connected to MongoDB.")
        except (ConnectionFailure, ServerSelectionTimeoutError) as e:
            print(f"MongoDB connection failed: {e}. Falling back to file-based database: {self.fallback_file}")
            self.use_mongo = False

    def _read_fallback(self):
        with self.lock:
            try:
                if os.path.exists(self.fallback_file):
                    with open(self.fallback_file, "r") as f:
                        return json.load(f)
            except Exception as e:
                print(f"Error reading fallback DB: {e}")
            return {"telemetry": [], "faults": [], "settings": {}}

    def _write_fallback(self, data):
        with self.lock:
            try:
                with open(self.fallback_file, "w") as f:
                    json.dump(data, f, indent=4, default=str)
            except Exception as e:
                print(f"Error writing fallback DB: {e}")

    def save_telemetry(self, data):
        record = {**data, "timestamp": datetime.now().isoformat()}
        if self.use_mongo:
            try:
                self.db.telemetry.insert_one(record)
                # Cap the collection at 500 documents for local performance
                if self.db.telemetry.count_documents({}) > 500:
                    oldest = self.db.telemetry.find().sort("timestamp", 1).limit(10)
                    for doc in oldest:
                        self.db.telemetry.delete_one({"_id": doc["_id"]})
            except Exception as e:
                print(f"Mongo write error: {e}")
        else:
            db_data = self._read_fallback()
            db_data["telemetry"].append(record)
            # Cap history size at 200 items in file mode to prevent massive files
            if len(db_data["telemetry"]) > 200:
                db_data["telemetry"] = db_data["telemetry"][-200:]
            self._write_fallback(db_data)

    def get_telemetry_history(self, limit=50):
        if self.use_mongo:
            try:
                cursor = self.db.telemetry.find({}, {"_id": 0}).sort("timestamp", -1).limit(limit)
                return list(cursor)[::-1] # return chronological order
            except Exception as e:
                print(f"Mongo read error: {e}")
        
        # Fallback mode
        db_data = self._read_fallback()
        return db_data["telemetry"][-limit:]

    def save_fault(self, fault_type, description, active=True, status="Critical"):
        fault_record = {
            "type": fault_type,
            "description": description,
            "active": active,
            "status": status,
            "timestamp": datetime.now().isoformat()
        }
        if self.use_mongo:
            try:
                if active:
                    self.db.faults.update_many({"active": True}, {"$set": {"active": False, "status": "Resolved"}})
                self.db.faults.insert_one(fault_record)
            except Exception as e:
                print(f"Mongo fault write error: {e}")
        else:
            db_data = self._read_fallback()
            if active:
                for f in db_data["faults"]:
                    if f.get("active", False):
                        f["active"] = False
                        f["status"] = "Resolved"
            db_data["faults"].append(fault_record)
            self._write_fallback(db_data)

    def update_fault_status(self, fault_type, new_status):
        if self.use_mongo:
            try:
                self.db.faults.update_many({"type": fault_type, "active": True}, {"$set": {"status": new_status}})
            except Exception as e:
                print(f"Mongo update fault status error: {e}")
        else:
            db_data = self._read_fallback()
            for f in db_data["faults"]:
                if f.get("type") == fault_type and f.get("active", False):
                    f["status"] = new_status
            self._write_fallback(db_data)

    def get_active_fault(self):
        if self.use_mongo:
            try:
                return self.db.faults.find_one({"active": True}, {"_id": 0})
            except Exception as e:
                print(f"Mongo fault read error: {e}")
        
        # Fallback mode
        db_data = self._read_fallback()
        for f in db_data["faults"]:
            if f.get("active", False):
                return f
        return None

    def clear_faults(self):
        if self.use_mongo:
            try:
                self.db.faults.update_many({"active": True}, {"$set": {"active": False, "status": "Resolved"}})
            except Exception as e:
                print(f"Mongo clear fault error: {e}")
        else:
            db_data = self._read_fallback()
            for f in db_data["faults"]:
                if f.get("active", False):
                    f["active"] = False
                    f["status"] = "Resolved"
            self._write_fallback(db_data)

    def get_faults_history(self):
        if self.use_mongo:
            try:
                cursor = self.db.faults.find({}, {"_id": 0}).sort("timestamp", -1)
                return list(cursor)
            except Exception as e:
                print(f"Mongo faults history read error: {e}")
        db_data = self._read_fallback()
        return db_data.get("faults", [])[::-1]

    def save_notification(self, notif_type, destination, message, status="Delivered"):
        notif_record = {
            "type": notif_type,
            "destination": destination,
            "message": message,
            "status": status,
            "timestamp": datetime.now().isoformat()
        }
        if self.use_mongo:
            try:
                self.db.notifications.insert_one(notif_record)
            except Exception as e:
                print(f"Mongo notification write error: {e}")
        else:
            db_data = self._read_fallback()
            if "notifications" not in db_data:
                db_data["notifications"] = []
            db_data["notifications"].append(notif_record)
            if len(db_data["notifications"]) > 100:
                db_data["notifications"] = db_data["notifications"][-100:]
            self._write_fallback(db_data)

    def get_notifications(self):
        if self.use_mongo:
            try:
                cursor = self.db.notifications.find({}, {"_id": 0}).sort("timestamp", -1)
                return list(cursor)
            except Exception as e:
                print(f"Mongo notifications read error: {e}")
        db_data = self._read_fallback()
        return db_data.get("notifications", [])[::-1]

    def save_settings(self, settings):
        if self.use_mongo:
            try:
                self.db.settings.update_one({}, {"$set": settings}, upsert=True)
            except Exception as e:
                print(f"Mongo settings write error: {e}")
        else:
            db_data = self._read_fallback()
            db_data["settings"].update(settings)
            self._write_fallback(db_data)

    def get_settings(self):
        default_settings = {
            "normal_flow_setpoint": 15.0,
            "max_pressure_threshold": 45.0,
            "target_water_level": 80.0
        }
        if self.use_mongo:
            try:
                data = self.db.settings.find_one({}, {"_id": 0})
                if data:
                    return {**default_settings, **data}
            except Exception as e:
                print(f"Mongo settings read error: {e}")
        
        db_data = self._read_fallback()
        return {**default_settings, **db_data.get("settings", {})}

    def get_assets(self):
        assets_file = os.path.join(os.path.dirname(__file__), "assets.json")
        try:
            with open(assets_file, "r") as f:
                seed_assets = json.load(f)
        except Exception as e:
            print(f"Error reading assets.json: {e}")
            seed_assets = []

        if self.use_mongo:
            try:
                # Seed collection if empty
                if self.db.assets.count_documents({}) == 0 and len(seed_assets) > 0:
                    self.db.assets.insert_many(seed_assets)
                cursor = self.db.assets.find({}, {"_id": 0})
                return list(cursor)
            except Exception as e:
                print(f"Mongo assets read error: {e}")
        
        return seed_assets

db = Database()
