# AetherTwin Phase 2: Active Digital Twin Enhancements

This plan outlines the implementation of improvements based on real-time feedback from oil and gas engineering professionals. It expands the static prototype into a feature-rich, enterprise-grade AI Operations Platform.

---

## User Review Required

> [!IMPORTANT]
> **Key Enhancements to Implement:**
> 1. **MFA & Alarm Escalation Management**: If a critical SCADA alarm is not manually acknowledged within 15 seconds (simulating a 15-minute SLA), the system will automatically escalate, highlighting a broadcast alert to plant directors.
> 2. **CMDB Asset Inventory**: We will seed a Configuration Management Database (CMDB) tracking Serial Numbers, Models, Manufacturers, and Vendors. AI diagnostics will reference this inventory to suggest exact replacement parts during failures.
> 3. **Long-Term Performance Degradation & Predictive Maintenance**: We will implement physical degradation equations in the simulator. The pump's health index will degrade based on runtime/workload, visualised on a new time-series health chart.
> 4. **Interactive AI Chat Assistant**: Operators can query live telemetry, asset serial numbers, or safety guides using a conversational interface.
> 5. **Hybrid DB & Real API Integration Toggle**: The backend will support `.env` files for real Azure DevOps and LLM APIs, falling back to mock layers if variables are missing.

---

## Open Questions

> [!NOTE]
> Please review and provide the following credentials when ready. You can paste them into a `.env` file inside `/backend` (we will create a template `.env.example`):
> *   **Azure DevOps**: PAT (Personal Access Token), Organization name, Project name.
> *   **LLM API**: OpenAI API Key or Gemini API Key. (We will use a secure routing client to handle whichever key you provide).

---

## Proposed Changes

We will build upon the existing code structure in `d:\practice_projects\PATAN`.

```
d:\practice_projects\PATAN\
├── backend\
│   ├── .env.example       # [NEW] Configuration template for credentials
│   ├── app.py             # [MODIFY] Register new endpoints (CMDB, chat, escalation, settings)
│   ├── simulator.py       # [MODIFY] Implement runtime degradation & health calculation
│   ├── ai_model.py        # [MODIFY] Add actual LLM caller, CMDB queries, and chat router
│   ├── db.py              # [MODIFY] Store asset inventory logs and chat history
│   └── assets.json        # [NEW] CMDB database seed (serial numbers, vendors, replacement URLs)
```

---

### Component 1: Python Backend Enhancements

#### [NEW] [backend/assets.json](file:///d:/practice_projects/PATAN/backend/assets.json)
Contains structured data for all assets (P-101, V-101, V-102, F-101) including Serial Numbers, Manufacturer specs, and purchase links.

#### [MODIFY] [backend/simulator.py](file:///d:/practice_projects/PATAN/backend/simulator.py)
- Adds a `health_index` (100% to 0%) for the Booster Pump.
- Vibration and friction during cavitation/clogging will accelerate the degradation rate of the pump's health index.
- Saves cumulative runtimes to the database.

#### [MODIFY] [backend/ai_model.py](file:///d:/practice_projects/PATAN/backend/ai_model.py)
- Integrates an actual HTTP request to OpenAI/Gemini APIs (if API keys exist in `.env`) to process telemetry contexts and return markdown diagnostics and PLC Structured Text overrides.
- Implements a natural language parser to handle user questions (chat assistant) related to CMDB assets or telemetry state.

#### [MODIFY] [backend/app.py](file:///d:/practice_projects/PATAN/backend/app.py)
Exposes endpoints:
- `/api/assets`: GET asset list / CMDB inventory.
- `/api/chat`: POST chat message to AI assistant.
- `/api/alarm/acknowledge`: POST to stop the escalation timer.

---

### Component 2: Angular Frontend Updates

We will update the Angular UI to expose these new capabilities visually.

#### [MODIFY] [frontend/src/app/app.html](file:///d:/practice_projects/PATAN/frontend/src/app/app.html) & [app.css](file:///d:/practice_projects/PATAN/frontend/src/app/app.css)
1. **SCADA Dashboard**: Add an **"Acknowledge Alarm"** button to the critical warning dialog. If clicked, the timer is cleared. If ignored, the dialog changes to a blinking red alert showing `"Escalating notification to Director of Operations."`
2. **AI Copilot Sidebar**: Add a **"Chat Assistant"** panel where users can converse with AetherTwin, showing interactive messages.
3. **Azure Twin / CMDB Panel**: Render an interactive table of the Asset Inventory showing specs, serial numbers, and vendor links.
4. **Analytics Hub**: Add a 5th rolling chart tracking **"Booster Pump Health Index (%)"** showing degradation.

---

## Verification Plan

### Automated Verification
- Run python tests verifying:
  - Anomaly escalation triggers when timer breaches 15s.
  - Pump degradation equations successfully decrement health.
  - Chat assistant routes questions to correct metadata tags.
- Compile Angular using `npm run build`.

### Manual Demo Verification
1. Start backend and frontend.
2. Trigger Cavitation. Wait 15 seconds without acknowledging -> Verify that the warning modal escalates to a broadcast warning.
3. Click "Acknowledge" -> Verify the alarm silences but the fault remains active for inspection.
4. Open the CMDB panel -> Verify Serial Numbers and Vendor specs are populated.
5. In the Chat Box, type `"What is the serial number of the pump?"` -> Verify the AI agent replies with the correct serial number from `assets.json`.
