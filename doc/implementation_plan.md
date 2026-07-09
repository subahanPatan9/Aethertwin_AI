# AetherTwin: AI-Powered Generative Digital Twin & Industrial Automation Copilot

AetherTwin is an **Engineering Intelligence** solution designed to bridge the gap between physical process plants and digital intelligence. It targets a multi-billion dollar problem in industrial engineering: the time-consuming process of onboarding legacy plants, detecting early-stage anomalies, performing root-cause analysis (RCA), and generating control logic dynamically.

This project will be built using a **modern fullstack stack** (Angular 21 frontend, Python/FastAPI backend, MongoDB/File-fallback database) optimized for a high-impact, live hackathon demonstration.

---

## User Review Required

> [!IMPORTANT]
> **Key Decisions & Target Architecture:**
> 1. **Zero-Config Database Fallback:** Since MongoDB might not be running or configured during the live presentation, the backend will feature an automated JSON file-based database fallback. This ensures the app is 100% stable during the live demo.
> 2. **AI Simulation vs API Dependency:** To avoid network failures during the hackathon, the AI Copilot (RCA and Structured Text generation) will use a highly optimized, context-aware rule engine that mimics an advanced vision-language model, with an option to connect to a real Azure OpenAI or Gemini endpoint if internet is available.
> 3. **Presentation Mode:** The Angular frontend will include a hidden/accessible "Presentation Control Center" overlay. This allows you, as the presenter, to step through the demo sequentially, trigger simulated errors, and show the AI's capabilities in a structured, flawless manner.

---

## Proposed Changes

We will create a multi-service structure within the workspace `d:\practice_projects\PATAN`.

```
d:\practice_projects\PATAN\
├── backend\                # Python FastAPI Backend
│   ├── app.py             # Main entry point
│   ├── simulator.py       # Physics-based plant simulator
│   ├── ai_model.py        # ML anomaly detector
│   ├── db.py              # MongoDB & local JSON database fallback
│   ├── requirements.txt   # Python dependencies
│   └── mock_data.json     # Initial database seed
│
└── frontend\               # Angular 21 Frontend
    ├── src\
    │   ├── app\
    │   │   ├── components\ # SCADA, Twin Editor, Presentation, Analytics, etc.
    │   │   └── services\   # API communications & telemetry state
    └── ...
```

---

### Component 1: Python FastAPI Backend

The backend acts as the physical engine and intelligence hub of the plant.

#### [NEW] [backend/requirements.txt](file:///d:/practice_projects/PATAN/backend/requirements.txt)
Specifies necessary dependencies: `fastapi`, `uvicorn`, `scikit-learn`, `numpy`, `pymongo`, `pydantic`.

#### [NEW] [backend/db.py](file:///d:/practice_projects/PATAN/backend/db.py)
Implements data storage. It attempts to connect to `mongodb://localhost:27017` but seamlessly falls back to reading/writing from a local file `db_fallback.json` if MongoDB is down.

#### [NEW] [backend/simulator.py](file:///d:/practice_projects/PATAN/backend/simulator.py)
A physics simulator for a water filtration loop.
- **Normal Operations**: Water flows from Tank 1 to Tank 2 through a pump and filter. Level, flow, pressure, temperature, and current are dynamically computed using physical formulas.
- **Fault States**:
  - **Pump Cavitation**: vibration spikes, motor temp rises, current fluctuates, flow drops.
  - **Pipe Leak**: inlet flow is high, outlet flow is low, pressure drops.
  - **Valve Clog**: pressure before valve spikes, flow drops, motor current spikes.

#### [NEW] [backend/ai_model.py](file:///d:/practice_projects/PATAN/backend/ai_model.py)
- Performs real-time anomaly detection (using a pre-trained scikit-learn model or mathematical threshold matrix for 100% deterministic demo control).
- Pinpoints the root cause and generates corresponding **IEC 61131-3 Structured Text (ST)** code overrides to bypass or safely shut down the system.

#### [NEW] [backend/app.py](file:///d:/practice_projects/PATAN/backend/app.py)
FastAPI endpoints to control simulation, read telemetry, trigger faults, query history, and request AI Copilot resolutions.

---

### Component 2: Angular 21 Frontend

A gorgeous, premium, dark-themed industrial interface built using Angular.

#### [NEW] [frontend](file:///d:/practice_projects/PATAN/frontend)
We will initialize a new Angular project. The visual hierarchy will include:
1. **Interactive SCADA Dashboard**: 
   - Uses an inline SVG layout showing animated water levels, rotating pump impellers, and glowing fluid flow lines.
   - Hover cards showing live sensors (FIT-101, PIT-101, LIT-101, VIT-101).
   - Control knobs for pump speed and valve position.
2. **AI Copilot Workspace**:
   - Sidebar with an "AI Chat" interface.
   - When a fault is triggered, the AI explains the issue, shows an interactive diagram of the fault location, and displays a generated PLC Structured Text code fix.
   - A button "Upload P&ID to Parse" that simulates visual parsing of a diagram and populates the SCADA configuration dynamically.
3. **Azure Twin & DTDL Center**:
   - Displays generated DTDL JSON files.
   - Shows live code snippets to deploy models, establish relationships, and upload properties to Azure Digital Twins.
4. **Presentation Assistant Panel**:
   - Built-in slide/checkpoint overlay to guide the presenter through a 5-minute pitch:
     - *Step 1: Normal Operation (Liquid flowing smoothly)*
     - *Step 2: Trigger Leak (Flow mismatch, line turns red)*
     - *Step 3: AI Diagnosis (Copilot explains leak, generates code)*
     - *Step 4: Auto-Mitigation (Shut off valve V-101)*
     - *Step 5: Export to Azure Digital Twins*

---

## Verification Plan

### Automated Tests
- Run Python tests using `pytest` to verify physics equations and anomaly classifications.
- Verify that Angular compiles correctly without errors via `npm run build`.

### Manual Verification & Demo Walkthrough
- Start Python backend (`python backend/app.py`).
- Start Angular frontend (`npm run start` or `ng serve`).
- Open browser, verify that normal telemetry runs (tank fills/drains).
- Click "Trigger Leak" -> Check if the pipe turns red and the AI Copilot immediately displays the correct analysis.
- Click "Apply AI Auto-Mitigation" -> Check if pump shuts down, leak stops, and safety ST code is applied.
