import time
import os
import base64
import urllib.request
import urllib.parse
import json

# Simple environment variables loader for .env files
def load_env_file():
    env_file = os.path.join(os.path.dirname(__file__), ".env")
    if os.path.exists(env_file):
        with open(env_file, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, val = line.split("=", 1)
                    os.environ[key.strip()] = val.strip()

# Initialize environment
load_env_file()

class AetherTwinAI:
    def __init__(self):
        # Load API keys from environment
        self.llm_key = os.environ.get("LLM_API_KEY", "")
        self.devops_user = os.environ.get("DEVOPS_USERNAME", "")
        self.devops_pass = os.environ.get("DEVOPS_PASSWORD", "")
        self.devops_org = os.environ.get("DEVOPS_ORGANIZATION", "hackathonindia")
        self.devops_proj = os.environ.get("DEVOPS_PROJECT", "AetherTwin")
        
        # Twilio API Credentials
        self.twilio_sid = os.environ.get("TWILIO_ACCOUNT_SID", "")
        self.twilio_token = os.environ.get("TWILIO_AUTH_TOKEN", "")
        self.twilio_from = os.environ.get("TWILIO_FROM_NUMBER", "")
        self.operator_phone = os.environ.get("OPERATOR_PHONE_NUMBER", "")

    def send_sms_alert(self, message):
        """
        Sends an SMS alert to the operator using Twilio's API via urllib.
        If credentials are missing, falls back to logging a clear visual message.
        """
        if not all([self.twilio_sid, self.twilio_token, self.twilio_from, self.operator_phone]):
            print(f"\n[MOCK SMS ALERT] To: {self.operator_phone or 'OPERATOR'} | Msg: {message}\n")
            return {"status": "mocked", "message": "Twilio credentials missing. Local fallback active."}
        
        url = f"https://api.twilio.com/2010-04-01/Accounts/{self.twilio_sid}/Messages.json"
        
        data = urllib.parse.urlencode({
            "To": self.operator_phone,
            "From": self.twilio_from,
            "Body": message
        }).encode("utf-8")
        
        req = urllib.request.Request(url, data=data, method="POST")
        
        # Twilio Basic Authentication (username=sid, password=token)
        auth_str = f"{self.twilio_sid}:{self.twilio_token}"
        auth_b64 = base64.b64encode(auth_str.encode("utf-8")).decode("utf-8")
        req.add_header("Authorization", f"Basic {auth_b64}")
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
        
        try:
            with urllib.request.urlopen(req, timeout=8) as response:
                res_body = response.read().decode("utf-8")
                print(f"[SMS ALERT SENT] Response: {res_body}")
                return json.loads(res_body)
        except Exception as e:
            print(f"[SMS ERROR] Failed to send alert: {e}")
            return {"status": "error", "error": str(e)}


    def analyze_telemetry(self, telemetry):
        """
        Uses a mathematically implemented Neural Network Autoencoder (for anomaly scoring)
        and a Multi-Layer Perceptron (MLP) Classifier (for fault categorization)
        to identify faults, confidence levels, and reconstruction error.
        """
        import math

        vibration = telemetry.get("motor_vibration", 0.0)
        temp = telemetry.get("motor_temp", 25.0)
        flow_in = telemetry.get("flow_fit101", 0.0)
        flow_out = telemetry.get("flow_fit102", 0.0)
        pressure = telemetry.get("pressure_pit101", 0.0)
        rpm = telemetry.get("pump_rpm", 0.0)
        current = telemetry.get("motor_current", 0.0)

        # 1. Normalization of inputs (Feature Scaling to [0, 1])
        x = [
            rpm / 3000.0,
            vibration / 10.0,
            temp / 100.0,
            flow_in / 20.0,
            flow_out / 20.0,
            pressure / 60.0,
            current / 10.0
        ]

        # Neural Network helper functions
        def dot_product(v1, v2):
            return sum(a * b for a, b in zip(v1, v2))

        def mat_vec_mul(matrix, vec, biases):
            return [dot_product(vec, row) + b for row, b in zip(matrix, biases)]

        def relu(vector):
            return [max(0.0, val) for val in vector]

        def sigmoid(vector):
            return [1.0 / (1.0 + math.exp(-max(-20.0, min(20.0, val)))) for val in vector]

        # 2. Unsupervised Autoencoder (Dimension reduction & Reconstruction)
        # Latent hidden layer representation (7 inputs -> 3 hidden units)
        encoder_weights = [
            [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],  # RPM feature
            [0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0],  # Temp feature
            [0.0, 0.0, 0.0, 0.5, 0.5, 0.0, 0.0]   # Flow balance feature
        ]
        encoder_biases = [0.0, 0.0, 0.0]

        # Reconstruction layer (3 hidden units -> 7 outputs)
        decoder_weights = [
            [1.0, 0.0, 0.0],  # Reconstructs RPM
            [0.1, 0.0, 0.0],  # Reconstructs normal vibration (scales with RPM)
            [0.0, 1.0, 0.0],  # Reconstructs temperature
            [0.0, 0.0, 1.0],  # Reconstructs flow_in
            [0.0, 0.0, 1.0],  # Reconstructs flow_out
            [0.3, 0.0, 0.0],  # Reconstructs normal pressure (scales with RPM)
            [0.2, 0.0, 0.0]   # Reconstructs normal current (scales with RPM)
        ]
        decoder_biases = [0.0, 0.05, 0.1, 0.0, 0.0, 0.05, 0.05]

        # Forward pass through Autoencoder
        hidden_ae = mat_vec_mul(encoder_weights, x, encoder_biases)
        hidden_ae_act = sigmoid(hidden_ae)
        reconstructed = mat_vec_mul(decoder_weights, hidden_ae_act, decoder_biases)
        
        # Calculate Reconstruction Error (MSE)
        recon_error = sum((a - b) ** 2 for a, b in zip(x, reconstructed)) / 7.0
        
        # Scale anomaly score based on reconstruction loss
        # RPM threshold ensures we don't flag shut-down states
        if rpm > 100:
            anomaly_score = min(100.0, recon_error * 800.0)
        else:
            anomaly_score = 0.0
            recon_error = 0.0

        # 3. Supervised MLP Classifier (7 inputs -> 5 hidden -> 4 output classes)
        # Class mapping: 0=NORMAL, 1=PUMP_CAVITATION, 2=PIPE_LEAK, 3=VALVE_CLOG
        classifier_w1 = [
            [0.0, 10.0, 0.0, 0.0, 0.0, 0.0, 0.0],       # Unit 0: Cavitation detector (High vibration)
            [0.0, 0.0, 0.0, 20.0, -20.0, -20.0, 0.0],   # Unit 1: Pipe leak detector
            [0.0, 0.0, 0.0, 0.0, -20.0, 20.0, 0.0],     # Unit 2: Valve clog detector
            [-10.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],      # Unit 3: Low speed/standby detector
            [0.0, 2.0, 2.0, 0.0, 0.0, 2.0, 0.0]         # Unit 4: General stress indicator
        ]
        classifier_b1 = [-5.0, -0.5, -12.0, 1.0, -2.0]

        classifier_w2 = [
            [-5.0, -5.0, -5.0, 5.0, -2.0],  # Logit for NORMAL
            [15.0, -5.0, -5.0, -5.0, 0.0],  # Logit for PUMP_CAVITATION
            [-5.0, 15.0, -5.0, -5.0, 0.0],  # Logit for PIPE_LEAK
            [-5.0, -5.0, 15.0, -5.0, 0.0]   # Logit for VALVE_CLOG
        ]
        classifier_b2 = [2.0, -2.0, -2.0, -2.0]

        # Forward pass through MLP
        hidden_cls = mat_vec_mul(classifier_w1, x, classifier_b1)
        hidden_cls_act = relu(hidden_cls)
        logits = mat_vec_mul(classifier_w2, hidden_cls_act, classifier_b2)

        # Softmax function to get class probabilities
        exp_logits = [math.exp(max(-20.0, min(20.0, val))) for val in logits]
        sum_exp = sum(exp_logits)
        probabilities = [val / sum_exp for val in exp_logits]

        # Get class with highest probability
        class_labels = ["NORMAL", "PUMP_CAVITATION", "PIPE_LEAK", "VALVE_CLOG"]
        max_idx = probabilities.index(max(probabilities))
        
        classification = class_labels[max_idx]
        confidence = probabilities[max_idx] * 100.0

        # Enforce standby override
        if rpm <= 300:
            classification = "NORMAL"
            confidence = 100.0

        # Check Capacity limits
        utilization = (rpm / 3000.0) * 100.0
        capacity_status = "NORMAL"
        capacity_message = "Equipment operating within design limits."
        
        if utilization > 90.0:
            capacity_status = "CRITICAL"
            capacity_message = f"🚨 AI ALERT: Booster pump speed utilization at {utilization:.1f}% exceeds 90% design SLA limit. Motor heat dissipation hazard."
        elif utilization > 75.0:
            capacity_status = "HIGH"
            capacity_message = f"⚠️ WARNING: Booster pump operating at {utilization:.1f}% capacity. Inspect downstream throttling."

        return {
            "classification": classification,
            "anomaly_score": round(anomaly_score, 2),
            "confidence": round(confidence, 1),
            "reconstruction_error": round(recon_error, 4),
            "capacity_status": capacity_status,
            "capacity_utilization": round(utilization, 2),
            "capacity_message": capacity_message
        }

    def get_mitigation_plan(self, fault_type):
        """
        Generates root cause analysis, mitigation recommendations, and 
        PLC Structured Text (IEC 61131-3) code to fix the issue.
        """
        plans = {
            "NORMAL": {
                "rca": "System is operating within normal technical bounds. No action required.",
                "mitigation": "Continue standard operations and monitor telemetry trends.",
                "plc_code": "(* Standard Operating Loop *)\nIF Pump_RPM_Setpoint > 0.0 THEN\n    Booster_Pump_Run := TRUE;\n    Inlet_Valve_V101_Cmd := 100.0;\n    Outlet_Valve_V102_Cmd := 100.0;\nELSE\n    Booster_Pump_Run := FALSE;\nEND_IF;",
                "dtdl_patch": {
                    "op": "replace",
                    "path": "/healthStatus",
                    "value": "HEALTHY"
                }
            },
            "PUMP_CAVITATION": {
                "rca": "### **Root Cause Analysis (RCA)**\n"
                       "- **Fault Detected**: Pump Cavitation (Vapour Bubble Collapse)\n"
                       "- **Trigger**: Suction side flow restriction. The inlet valve **V-101** is closed or choked, preventing fluid from entering the impeller housing while the pump runs at high RPM.\n"
                       "- **Physical Symptoms**: High localized frictional heat (**Motor Temp > 70°C**), excessive mechanical stress (**Vibration > 8.0 mm/s**), and motor load instability.\n"
                       "- **Impact**: High risk of permanent impeller pitting, seal failure, and motor winding burnout within hours.",
                "mitigation": "1. **Emergency Interlock**: Shut down the Booster Pump (P-101) immediately.\n"
                              "2. **Safety Bypass**: Open the inlet suction valve (V-101) fully.\n"
                              "3. **Recirculation Valve**: Enable recirculation/vent valve to purge any trapped air/vapor lock.\n"
                              "4. **Restart Sequence**: Restart pump only when suction pressure is confirmed > 5 PSI.",
                "plc_code": "(* EMERGENCY CAVITATION MITIGATION BLOCK *)\n"
                            "(* Triggered by AI Anomaly Monitor *)\n"
                            "VAR\n"
                            "    CavitationDetected : BOOL := TRUE;\n"
                            "    PurgeTimer : TON;\n"
                            "END_VAR\n\n"
                            "IF CavitationDetected THEN\n"
                            "    (* 1. Immediate Pump Shutdown *)\n"
                            "    Booster_Pump_Run := FALSE;\n"
                            "    Booster_Pump_RPM_Cmd := 0.0;\n"
                            "    \n"
                            "    (* 2. Force Open Suction Valve to Refill Head *)\n"
                            "    Inlet_Valve_V101_Cmd := 100.0;\n"
                            "    \n"
                            "    (* 3. Raise Alarm Flag *)\n"
                            "    System_Alarm_Code := 102; // Cavitation Lockout\n"
                            "    \n"
                            "    (* 4. Trigger Alarm Output *)\n"
                            "    Horn_Strobe := TRUE;\n"
                            "END_IF;",
                "dtdl_patch": {
                    "op": "replace",
                    "path": "/healthStatus",
                    "value": "CRITICAL_CAVITATION"
                }
            },
            "PIPE_LEAK": {
                "rca": "### **Root Cause Analysis (RCA)**\n"
                       "- **Fault Detected**: Pipe Fracture / Fluid Leakage\n"
                       "- **Trigger**: Significant mass-flow differential. Flow transmitter **FIT-101** (pump discharge) is measuring high flow, but **FIT-102** (filter inlet) is reading extremely low flow.\n"
                       "- **Physical Symptoms**: Discharge pressure **PIT-101** dropped to near 0, while T-101 level drops rapidly without increasing T-102 level.\n"
                       "- **Impact**: Severe water loss, flooding of the facility basement, and potential damage to electrical components due to spraying liquid.",
                "mitigation": "1. **Emergency Isolation**: Shut down Booster Pump (P-101) immediately.\n"
                              "2. **Line Depressurization**: Close Outlet Valve (V-102) to prevent reverse siphon flow from the product tank.\n"
                              "3. **Isolate Source**: Close Inlet Valve (V-101) to cut off supply.\n"
                              "4. **Notification**: Open Azure DevOps maintenance ticket to replace pipeline gasket.",
                "plc_code": "(* PIPELINE LEAK ISOLATION BLOCK *)\n"
                            "(* Triggered by FIT-101/102 Flow Mismatch *)\n"
                            "VAR\n"
                            "    LeakDetected : BOOL := TRUE;\n"
                            "END_VAR\n\n"
                            "IF LeakDetected THEN\n"
                            "    (* 1. Kill Pump to stop feeding the leak *)\n"
                            "    Booster_Pump_Run := FALSE;\n"
                            "    Booster_Pump_RPM_Cmd := 0.0;\n"
                            "    \n"
                            "    (* 2. Close isolation valves on both sides *)\n"
                            "    Inlet_Valve_V101_Cmd := 0.0;\n"
                            "    Outlet_Valve_V102_Cmd := 0.0;\n"
                            "    \n"
                            "    (* 3. System Lockout and Alert *)\n"
                            "    System_Alarm_Code := 204; // Pipeline Leak\n"
                            "    Leak_Siren := TRUE;\n"
                            "END_IF;",
                "dtdl_patch": {
                    "op": "replace",
                    "path": "/healthStatus",
                    "value": "CRITICAL_LEAK"
                }
            },
            "VALVE_CLOG": {
                "rca": "### **Root Cause Analysis (RCA)**\n"
                       "- **Fault Detected**: Line Blockage / Valve Clogging\n"
                       "- **Trigger**: Deadhead condition. Flow is blocked down-stream (valve **V-102** or Sand Filter **F-101** is clogged).\n"
                       "- **Physical Symptoms**: Pressure sensor **PIT-101** spiked to **> 55 PSI** (critical limit), while pump motor current draw spiked to **> 6.5 Amps** due to extreme back-pressure workload.\n"
                       "- **Impact**: High risk of pipeline rupture, filter housing fracture, or pump motor overheating.",
                "mitigation": "1. **Interlock Trip**: Shut down Booster Pump (P-101) to relieve pressure.\n"
                              "2. **Pressure Relief**: Trigger a relief valve or open the bypass loop.\n"
                              "3. **Backwash Cycle**: Initiate automated Sand Filter backwash cycle to clear sediment.\n"
                              "4. **Inspection**: Verify valve V-102 physical actuator position.",
                "plc_code": "(* DEADHEAD PRESSURE PROTECTION BLOCK *)\n"
                            "(* Triggered by PIT-101 High Pressure Trip *)\n"
                            "VAR\n"
                            "    HighPressureTrip : BOOL := TRUE;\n"
                            "    BackwashSequence : BOOL := FALSE;\n"
                            "END_VAR\n\n"
                            "IF HighPressureTrip THEN\n"
                            "    (* 1. Trip Pump on High-High Pressure *)\n"
                            "    Booster_Pump_Run := FALSE;\n"
                            "    Booster_Pump_RPM_Cmd := 0.0;\n"
                            "    \n"
                            "    (* 2. Trigger automated filter backwash *)\n"
                            "    BackwashSequence := TRUE;\n"
                            "    Backwash_Valve_Cmd := 100.0;\n"
                            "    \n"
                            "    (* 3. Set alarms *)\n"
                            "    System_Alarm_Code := 308; // High Pressure Lockout\n"
                            "END_IF;",
                "dtdl_patch": {
                    "op": "replace",
                    "path": "/healthStatus",
                    "value": "CRITICAL_BLOCKAGE"
                }
            }
        }
        return plans.get(fault_type, plans["NORMAL"])

    def generate_llm_diagnostics(self, fault_type: str, telemetry: dict) -> dict:
        """
        Uses the configured LLM API Key to fetch dynamic diagnostics and interlock code,
        falling back to local rule-based diagnostics if unauthorized or offline.
        """
        self.llm_key = os.environ.get("LLM_API_KEY", "")
        if not self.llm_key:
            # Fall back to local rules
            return self.get_mitigation_plan(fault_type)

        # Standard OpenAI API request template
        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.llm_key}"
        }
        
        # Prepare prompt
        prompt = f"""
        You are AetherTwin Industrial Safety AI. Review the following sensor readings for anomaly flag {fault_type}:
        - Pump RPM: {telemetry.get('pump_rpm')}
        - Vibration: {telemetry.get('motor_vibration')} mm/s
        - Temperature: {telemetry.get('motor_temp')} C
        - Discharge Flow: {telemetry.get('flow_fit101')} L/min
        - Outlet Flow: {telemetry.get('flow_fit102')} L/min
        - Line Pressure: {telemetry.get('pressure_pit101')} PSI
        - Current Draw: {telemetry.get('motor_current')} A

        Generate a JSON response containing:
        1. "rca": Detailed Root Cause Analysis in markdown format.
        2. "mitigation": Step-by-step mitigation recommendations.
        3. "plc_code": Structured Text override program to resolve the state.
        4. "dtdl_patch": A single DTDL replacement patch block.
        """

        payload = {
            "model": "gpt-3.5-turbo",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.2
        }

        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers=headers,
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=5) as response:
                res_data = json.loads(response.read().decode("utf-8"))
                content = res_data["choices"][0]["message"]["content"]
                parsed = json.loads(content)
                return {
                    "rca": parsed.get("rca"),
                    "mitigation": parsed.get("mitigation"),
                    "plc_code": parsed.get("plc_code"),
                    "dtdl_patch": parsed.get("dtdl_patch", {"op": "replace", "path": "/healthStatus", "value": "CRITICAL"})
                }
        except Exception as e:
            # Azure OpenAI format fallback or local fallback
            print(f"LLM API Call failed ({e}). Using local high-fidelity rules.")
            return self.get_mitigation_plan(fault_type)

    def create_azure_devops_workitem(self, component_id: str, fault_type: str, priority: str, description: str):
        """
        Creates a real work item in Azure DevOps if credentials are provided,
        otherwise falls back to generating a mock ticket.
        """
        self.devops_user = os.environ.get("DEVOPS_USERNAME", "")
        self.devops_pass = os.environ.get("DEVOPS_PASSWORD", "")
        self.devops_org = os.environ.get("DEVOPS_ORGANIZATION", "hackathonindia")
        self.devops_proj = os.environ.get("DEVOPS_PROJECT", "AetherTwin")
        
        if not self.devops_user or not self.devops_pass:
            print("DevOps Credentials missing from .env. Generating mock ticket.")
            return None

        # Build Azure DevOps work item REST endpoint URL
        # We will create a "Task" type work item
        url = f"https://dev.azure.com/{self.devops_org}/{self.devops_proj}/_apis/wit/workitems/$Task?api-version=6.0"
        
        priority_val = 2
        if priority == "HIGH" or priority == "CRITICAL":
            priority_val = 1
        elif priority == "LOW":
            priority_val = 3

        # Prepare JSON patch payload
        payload = [
            {
                "op": "add",
                "path": "/fields/System.Title",
                "value": f"[AetherTwin Alarm] Critical Fault detected: {fault_type} on {component_id}"
            },
            {
                "op": "add",
                "path": "/fields/System.Description",
                "value": f"Root Cause Analysis:<br/>{description.replace('\n', '<br/>')}<br/><br/><i>Created automatically by AetherTwin Agentic AI.</i>"
            },
            {
                "op": "add",
                "path": "/fields/Microsoft.VSTS.Common.Priority",
                "value": priority_val
            }
        ]
        
        # Prepare headers with basic auth
        auth_str = f"{self.devops_user}:{self.devops_pass}"
        auth_bytes = auth_str.encode("utf-8")
        encoded_auth = base64.b64encode(auth_bytes).decode("utf-8")
        
        headers = {
            "Content-Type": "application/json-patch+json",
            "Authorization": f"Basic {encoded_auth}"
        }
        
        try:
            req = urllib.request.Request(
                url, 
                data=json.dumps(payload).encode("utf-8"), 
                headers=headers, 
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=8) as response:
                res_data = json.loads(response.read().decode("utf-8"))
                real_id = res_data.get("id")
                real_url = res_data.get("_links", {}).get("html", {}).get("href", "")
                print(f"Azure DevOps: Successfully created real work item #{real_id}")
                return {
                    "ticket_id": f"WO-{real_id}",
                    "url": real_url
                }
        except Exception as e:
            print(f"Azure DevOps API call failed: {e}. Falling back to mock ticket.")
            return None

    def run_chat_query(self, query: str, live_data: dict, assets_list: list) -> str:
        """
        Parses operator chat queries in real-time, matching against CMDB database,
        live telemetry parameters, or safety guidelines. If LLM_API_KEY is present,
        it uses the LLM to provide a highly contextual response about the entire project.
        """
        self.llm_key = os.environ.get("LLM_API_KEY", "")
        
        # If LLM key is available, leverage it for comprehensive project-related Q&A
        if self.llm_key:
            url = "https://api.openai.com/v1/chat/completions"
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.llm_key}"
            }
            
            # Formulate the entire system and project context
            project_context = f"""
            You are the AetherTwin Safety Copilot, an advanced Generative AI Assistant for the AetherTwin project.
            Here is the complete context of the AetherTwin project to help you answer the user's query:

            PROJECT OVERVIEW:
            - AetherTwin is an AI-powered Generative Digital Twin & Industrial Automation Copilot.
            - It monitors a physical water filtration loop, classifies faults, mitigates hazards automatically, and exports models to Azure Digital Twins.
            
            KEY FEATURES & INTERFACE TABS:
            1. SCADA Simulator: Displays a gorgeous, premium, 3D-styled SVG plant digital twin. Shows live telemetry (RPM, flow, pressure, vibration, temperature, current) and provides hardware fault injection (Pump Cavitation, Discharge Pipe Leak, Downstream Blockage).
            2. AI RCA (Diagnostics): Displays the active root-cause analysis, mitigation plans, and generates IEC 61131-3 Structured Text PLC safety code dynamically to isolate/resolve active faults.
            3. Issue Log: Tracks historical and current system faults with a status workflow (Critical -> In Progress -> Resolved). Includes a slide-out Forensic Incident Report drawer containing telemetry snapshots, alarms, and complete timelines.
            4. Azure Digital Twin (DTDL): Generates Digital Twin Definition Language (DTDL v2) model interfaces and pushes properties to Azure cloud twins.
            5. Analytics Hub: Renders SVG rolling charts tracking vibration, pressure, inflow/outflow, and motor temp.
            6. System Flow Diagram: Displays an interactive engineering flowchart mapping edge telemetry, FastAPI server engines, autoencoder diagnostics, Azure Digital Twins, Twilio notifications, and DevOps boards.
            7. Sync Config: A settings form to adjust telemetry polling rates, thresholds, and Twilio SMS alarm gateway credentials. It also displays the notification history audit log (Simulated SMS alerts, DevOps tickets, emails).

            LIVE TELEMETRY:
            {json.dumps(live_data.get('telemetry', {}), indent=2)}

            CMDB ASSETS DATABASE:
            {json.dumps(assets_list, indent=2)}

            USER QUERY:
            {query}

            INSTRUCTIONS:
            - Provide a clear, helpful, and comprehensive response.
            - You can answer questions about the project's UI, the SCADA system, specific assets (serial numbers, models), telemetry values, safety mitigations, DTDL models, Twilio settings, or the general project architecture.
            - Keep your tone professional, industrial, and helpful. Use markdown format.
            """

            payload = {
                "model": "gpt-3.5-turbo",
                "messages": [
                    {"role": "system", "content": "You are a professional industrial engineering AI assistant."},
                    {"role": "user", "content": project_context}
                ],
                "temperature": 0.4
            }

            try:
                req = urllib.request.Request(
                    url,
                    data=json.dumps(payload).encode("utf-8"),
                    headers=headers,
                    method="POST"
                )
                with urllib.request.urlopen(req, timeout=8) as response:
                    res_data = json.loads(response.read().decode("utf-8"))
                    content = res_data["choices"][0]["message"]["content"]
                    return content
            except Exception as e:
                print(f"Chat LLM query failed: {e}. Falling back to rule-based parser.")

        query_lower = query.lower().strip()
        
        # Spare parts / Bearing assistant query parsing (Point 10)
        if "bearing" in query_lower or "spare" in query_lower or "part" in query_lower:
            matched_asset = None
            for asset in assets_list:
                asset_id_raw = asset["id"].lower()
                asset_id_spaced = asset_id_raw.replace("-", " ")
                asset_pump_num = "pump-" + asset_id_raw.split("-")[1] if "-" in asset_id_raw else ""
                asset_pump_num_spaced = "pump " + asset_id_raw.split("-")[1] if "-" in asset_id_raw else ""
                
                if (asset_id_raw in query_lower or 
                    asset_id_spaced in query_lower or 
                    (asset_pump_num and asset_pump_num in query_lower) or 
                    (asset_pump_num_spaced and asset_pump_num_spaced in query_lower) or
                    asset["name"].lower() in query_lower):
                    matched_asset = asset
                    break
            
            if matched_asset:
                spares = matched_asset.get("installed_spare_parts", [])
                if spares:
                    bearing_spares = [s for s in spares if "bearing" in s.get("part_name", "").lower()]
                    
                    res = f"### 📦 Spare Parts Inventory: **{matched_asset['name']}**\n"
                    if "bearing" in query_lower:
                        if bearing_spares:
                            res += "The following bearing components are currently installed:\n\n"
                            for s in bearing_spares:
                                res += f"- 🔘 **{s['part_name']}**\n"
                                res += f"  - **Part Number**: `{s['part_number']}`\n"
                                res += f"  - **Approved Vendor**: {s['vendor']}\n"
                                res += f"  - **Quantity**: {s.get('quantity', 1)}\n"
                        else:
                            res += "No bearing components are installed in this equipment.\n"
                    else:
                        res += "Installed spare parts catalog:\n\n"
                        for s in spares:
                            res += f"- ⚙️ **{s['part_name']}** (P/N: `{s['part_number']}`, Vendor: {s['vendor']})\n"
                    
                    res += f"\n📞 **Vendor Contact**: {matched_asset.get('vendor_contacts', 'N/A')}"
                    return res
                else:
                    return f"No spare parts listed for **{matched_asset['name']}**."
        
        # 1. Asset/CMDB queries
        if "serial" in query_lower or "asset" in query_lower or "part" in query_lower or "model" in query_lower or "vendor" in query_lower:
            matched_asset = None
            for asset in assets_list:
                if asset["id"].lower() in query_lower or asset["name"].lower() in query_lower or ("pump" in query_lower and "P-101" in asset["id"]):
                    matched_asset = asset
                    break
            
            if matched_asset:
                return (
                    f"### CMDB Asset Record: **{matched_asset['name']} ({matched_asset['id']})**\n"
                    f"- **Serial Number**: `{matched_asset['serial_number']}`\n"
                    f"- **Model**: {matched_asset['model']}\n"
                    f"- **Manufacturer**: {matched_asset['manufacturer']}\n"
                    f"- **Vendor**: {matched_asset['vendor']}\n"
                    f"- **Installation Date**: {matched_asset['installation_date']}\n"
                    f"- **Last Maintenance**: {matched_asset['last_maintenance']}\n"
                    f"- **Link to OEM Spec**: [OEM Datasheet]({matched_asset['replacement_url']})"
                )
            
            res = "### Plant Asset Inventory (CMDB)\n"
            for asset in assets_list:
                res += f"- **{asset['id']}**: {asset['name']} (S/N: `{asset['serial_number']}`, Model: {asset['model']})\n"
            return res

        # 2. Live Telemetry queries
        if "telemetry" in query_lower or "live" in query_lower or "status" in query_lower or "rpm" in query_lower or "pressure" in query_lower or "vibration" in query_lower or "temperature" in query_lower or "flow" in query_lower or "health" in query_lower:
            telemetry = live_data.get("telemetry", {})
            active_fault = telemetry.get("active_fault", "NORMAL")
            
            status_text = "🟢 **SYSTEM STABLE**" if active_fault == "NORMAL" else f"🔴 **CRITICAL ALARM DETECTED: {active_fault}**"
            
            return (
                f"### Current Telemetry & Operational Health Status\n"
                f"- **Overall System State**: {status_text}\n"
                f"- **Booster Pump Speed**: {telemetry.get('pump_rpm', 0)} RPM\n"
                f"- **Vibration Intensity**: {telemetry.get('motor_vibration', 0)} mm/s\n"
                f"- **Discharge Pressure**: {telemetry.get('pressure_pit101', 0)} PSI\n"
                f"- **Inflow (FIT-101)**: {telemetry.get('flow_fit101', 0)} L/min\n"
                f"- **Outflow (FIT-102)**: {telemetry.get('flow_fit102', 0)} L/min\n"
                f"- **Pump Temperature**: {telemetry.get('motor_temp', 0)} °C\n"
                f"- **Pump Health Index**: {telemetry.get('pump_health_index', 100.0)}%\n"
                f"- **Cumulative Running Time**: {telemetry.get('cumulative_runtime', 0)} seconds"
            )

        # 3. Anomaly / Troubleshooting guides
        if "cavitation" in query_lower or "leak" in query_lower or "clog" in query_lower or "deadhead" in query_lower or "fix" in query_lower or "mitigate" in query_lower:
            fault_flag = "PUMP_CAVITATION"
            if "leak" in query_lower:
                fault_flag = "PIPE_LEAK"
            elif "clog" in query_lower or "deadhead" in query_lower:
                fault_flag = "VALVE_CLOG"
                
            plan = self.get_mitigation_plan(fault_flag)
            return (
                f"### Safety Operations Manual: **{fault_flag.replace('_', ' ')}**\n"
                f"**RCA Summary**:\n{plan['rca']}\n\n"
                f"**Emergency Procedure**:\n{plan['mitigation']}"
            )

        # Default help text
        return (
            "Hello! I am your generative AetherTwin AI Assistant. You can ask me:\n\n"
            "1. 🗄️ **CMDB queries**: *'What is the serial number of Pump P-101?'* or *'Show asset list'*\n"
            "2. 📊 **Telemetry queries**: *'What is the current pump speed?'* or *'Show live status'*\n"
            "3. 🚨 **Safety troubleshooting**: *'How do I mitigate pump cavitation?'*\n"
        )

ai_engine = AetherTwinAI()
