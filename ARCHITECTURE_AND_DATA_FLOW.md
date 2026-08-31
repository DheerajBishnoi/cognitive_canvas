# 🧠 Cognitive Canvas: Architecture & Data Flow Guide

This document explains **how data moves between the Frontend, the Backend Server, the AI Agents, and the Database (Firestore)** in Cognitive Canvas.

---

## 🌟 The Big Picture (Simple Analogy)

Think of Cognitive Canvas like a **smart restaurant**:

1. **The Customer (Frontend / React UI):** You sit at the table and say: *"Plan my 2-week Linux study schedule."*
2. **The Waiter (FastAPI Unified Server):** Takes your order from the table to the kitchen via a secure tray (REST APIs & Server-Sent Events).
3. **The Head Chef (`root_agent`):** Doesn't cook everything immediately. Instead, writes down an organized ticket: *"New Linux Project with Goal X"* and posts it on the order board (Firestore Database).
4. **The Order Dispatcher (`event_dispatcher.py`):** Constantly watches the order board in the background. As soon as a new ticket appears, passes it to the specialized cooks.
5. **The Specialist Cooks (`router_agent`, `planner_agent`, `research_agent`):**
   * The **Router** reads the ticket and decides who should do the work.
   * The **Planner** breaks the goal down into specific, dated study tasks (e.g. *"Read chapter 1 on Day 1"*).
   * The **Researcher** looks up books and tutorials using Google Search.
6. **The Menu Board (Firestore Database):** Stores all projects and tasks.
7. **The Live Screen (Frontend Dashboard & Calendar):** Automatically updates in real time so the customer sees their generated schedule and can check off tasks as they finish them!

---

## 🏗️ Architecture Diagram

```mermaid
flowchart TD
    subgraph Browser["🖥️ Client Browser (React + Vite)"]
        UI["React UI (Dashboard, Calendar, Agent Sidebar)"]
        API_CLIENT["api.js (REST Client & SSE Stream Listener)"]
    end

    subgraph Backend["⚙️ Backend Server (FastAPI on Port 8000)"]
        PROXY["Vite Proxy (/api -> http://127.0.0.1:8000)"]
        FASTAPI["server.py (FastAPI)"]
        CASCADE["Model Fallback Engine (3.5 -> 3.1 -> 2.5)"]
        ROOT_AGENT["root_agent (Extraction Agent)"]
    end

    subgraph Database["☁️ Google Cloud Firestore"]
        COL_PROJECTS[("projects Collection")]
        COL_TASKS[("tasks Collection")]
        COL_EVENTS[("events Collection")]
        COL_RESEARCH[("research_results Collection")]
    end

    subgraph BackgroundWorker["🤖 Background Agent Worker"]
        DISPATCHER["event_dispatcher.py (Polling Loop)"]
        ROUTER["router_agent"]
        PLANNER["planner_agent"]
        RESEARCHER["research_agent"]
    end

    %% Client to Server Flow
    UI -->|User types message| API_CLIENT
    API_CLIENT -->|HTTP /api/chat & /api/projects| PROXY
    PROXY --> FASTAPI

    %% Server to Agents & DB
    FASTAPI --> CASCADE
    CASCADE --> ROOT_AGENT
    ROOT_AGENT -->|Saves new Project & Event| Database

    %% Background Processing
    DISPATCHER -->|1. Polls PENDING Events| COL_EVENTS
    DISPATCHER -->|2. Dispatches Event| ROUTER
    ROUTER -->|Transfers Context| PLANNER
    ROUTER -->|Transfers Context| RESEARCHER
    PLANNER -->|3. Writes Actionable Tasks| COL_TASKS
    RESEARCHER -->|3. Writes Findings| COL_RESEARCH
    DISPATCHER -->|4. Marks Event COMPLETED| COL_EVENTS

    %% Data Sync back to UI
    FASTAPI -->|Reads Live Projects, Tasks, Schedule| Database
    FASTAPI -.->|SSE Stream Tokens & Fallback Alerts| API_CLIENT
    API_CLIENT -.->|Auto-refresh Data| UI
```

---

## 🧩 The 4 Main Components

| Component | Technology | Role in the System |
| :--- | :--- | :--- |
| **1. Frontend** | React, Vite, Tailwind CSS | The visual user interface. Displays Project cards, the 1-year interactive Calendar, and the collapsible AI Chat Sidebar. |
| **2. Unified Server** | Python, FastAPI, Uvicorn (`server.py`) | Acts as the central gateway. Manages REST APIs (`/api/projects`, `/api/schedule`, `/api/tasks`) and streams AI chat with automatic model fallback (`/api/chat`). |
| **3. Database** | Google Cloud Firestore | Cloud NoSQL database holding all persistent data across 4 collections: `projects`, `tasks`, `events`, and `research_results`. |
| **4. Multi-Agent Engine** | Google ADK & Gemini 3.5 Flash | Intelligent background workers (`event_dispatcher.py`, `router_agent`, `planner_agent`, `research_agent`) that decompose large goals into schedules and conduct web research. |

---

## 🔄 End-to-End Data Flows

### Flow 1: When a User Sends a Goal / Plan Request

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant Frontend as React Frontend (App.jsx)
    participant Server as FastAPI Server (server.py)
    participant Gemini as Gemini AI (3.5 / 3.1 / 2.5)
    participant DB as Cloud Firestore
    participant Dispatcher as event_dispatcher.py
    participant Planner as planner_agent

    User->>Frontend: Types "Plan to study Operating Systems in 2 weeks"
    Frontend->>Server: POST /api/chat (SSE Stream)
    Server->>Gemini: Sends prompt to root_agent
    alt Primary Quota Exhausted (429)
        Server-->>Frontend: SSE event: {"type": "fallback_warning", "to_model": "gemini-3.1-flash-lite"}
        Server->>Gemini: Re-runs request on Gemini 3.1 Flash Lite
    end
    Gemini-->>Server: Returns structured extraction (intent: "plan")
    Server->>DB: 1. Creates Project in `projects` collection<br/>2. Creates Event (PLAN_REQUESTED, status: PENDING) in `events`
    Server-->>Frontend: Streams final reply: "I've started planning your Operating Systems project!"
    
    Note over Dispatcher,Planner: Asynchronous Background Processing
    loop Every 5 Seconds
        Dispatcher->>DB: Query `events` where status == "PENDING"
    end
    Dispatcher->>DB: Marks Event as "PROCESSING"
    Dispatcher->>Planner: Routes event payload to planner_agent
    Planner->>Planner: Decomposes goal into daily milestones
    Planner->>DB: Writes tasks into `tasks` collection (title, due_date, priority)
    Dispatcher->>DB: Marks Event as "COMPLETED"

    Note over Frontend,DB: Automatic UI Update
    Frontend->>Server: GET /api/projects & GET /api/schedule
    Server->>DB: Reads new Projects & Tasks
    Server-->>Frontend: Returns updated data
    Frontend->>User: Displays new Project Card & Tasks on the Calendar!
```

---

### Flow 2: How the Calendar & Schedule View Works

1. **1-Year Generation:** The React frontend automatically computes a 12-month calendar horizon (from current date through 1 year ahead).
2. **Task Mapping by Date:**
   * When `GET /api/schedule` is fetched, the frontend receives all tasks with their `due_date` (e.g. `2026-08-30`, `2026-09-14`).
   * For every date on the calendar, if tasks exist for that date, a **blue indicator dot** is drawn under the date number (or a **green dot** if all tasks for that day are marked completed).
3. **Date Selection & Filtering:**
   * **Clicking Today:** Shows tasks due today + any unassigned active backlog tasks.
   * **Clicking a Specific Future Date:** Filters and displays only tasks scheduled for that exact date (`task.dueDate === selectedDate`).
   * **Clicking a Past Date:** Displays tasks completed or scheduled on that past date.
4. **Quick-Add Task:**
   * Typing in `+ Add task for [Selected Date]...` sends a `POST /api/tasks` request to `server.py`, which writes directly to Firestore and updates both the schedule list and the calendar dot live.

---

### Flow 3: Checking Off / Completing a Task

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant Frontend as React UI
    participant Server as FastAPI Server
    participant DB as Cloud Firestore

    User->>Frontend: Clicks checkbox on "Complete chapter 1"
    Frontend->>Frontend: Optimistically toggles checkbox (instant visual feedback)
    Frontend->>Server: PATCH /api/tasks/{task_id} with {"done": true}
    Server->>DB: Updates task document in `tasks` collection (status: "completed")
    Server-->>Frontend: Returns {"status": "success"}
    Frontend->>Frontend: Re-fetches /api/projects to update project completion badge (e.g. "3/5 tasks")
```

---

### Flow 4: Automatic Quota Fallback (3.5 ➔ 3.1 ➔ 2.5)

```mermaid
flowchart LR
    REQ["Incoming User Prompt"] --> M1{"Gemini 3.5 Flash<br/>(Primary)"}
    M1 -->|Success 200| RES["Return Output to User"]
    M1 -->|Quota Error 429| F1["⚡ Emit Fallback Alert Banner"]
    F1 --> M2{"Gemini 3.1 Flash Lite<br/>(Fallback 1)"}
    M2 -->|Success 200| RES
    M2 -->|Quota Error 429| F2["⚡ Emit Fallback Alert Banner"]
    F2 --> M3{"Gemini 2.5 Flash<br/>(Fallback 2)"}
    M3 -->|Success 200| RES
    M3 -->|All Failed| ERR["Show Friendly Error Notice"]
```

* **No Crashes:** If your Gemini 3.5 Flash rate limit is hit, the user doesn't see a raw server crash or 500 error.
* **Instant Re-route:** The server catches `429` / `RESOURCE_EXHAUSTED`, sends a warning banner to the UI sidebar, and immediately completes the query using the next model in line.

---

## 🗄️ Firestore Database Schema Reference

```
negnq-agenticassistant (Firestore Project)
│
├── 📂 projects/
│   └── 📄 {project_id}
│       ├── title: string (e.g. "Linux Learning Curriculum")
│       ├── summary: string (e.g. "Comprehensive 2-week plan for Linux...")
│       ├── deadline: string | null
│       └── status: "active" | "completed"
│
├── 📂 tasks/
│   └── 📄 {task_id}
│       ├── project_id: string (links to parent project)
│       ├── title: string (e.g. "Read Chapter 1: Introduction to Kernels")
│       ├── task_type: "reading" | "research" | "study" | "task"
│       ├── priority: "high" | "medium" | "low"
│       ├── due_date: string (ISO date e.g. "2026-08-30")
│       ├── estimated_minutes: number (e.g. 90)
│       ├── details: string
│       └── status: "queued" | "in-progress" | "completed"
│
├── 📂 events/
│   └── 📄 {event_id}
│       ├── type: "PLAN_REQUESTED" | "TASK_CREATED" | "RESEARCH_REQUESTED"
│       ├── entity_id: string
│       ├── payload: dict (raw event parameters)
│       ├── status: "PENDING" | "PROCESSING" | "COMPLETED" | "FAILED"
│       └── attempt_count: number
│
└── 📂 research_results/
    └── 📄 {result_id}
        ├── project_id: string
        ├── query: string
        ├── summary: string (researched findings)
        └── status: "COMPLETED"
```

---

## 🚀 How to Run the Whole Stack

Open **3 terminals**:

```bash
# Terminal 1: Backend API & AI Server
cd cognitive_canvas/cognitive_canvas
python3 server.py

# Terminal 2: Background Multi-Agent Dispatcher
cd cognitive_canvas/cognitive_canvas/services
python3 event_dispatcher.py

# Terminal 3: React Frontend Web UI
cd frontend
npm run dev
```

Visit `http://localhost:5173` in any browser!
