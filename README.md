# Mater

A real-time, voice-first vehicle assistant. Live OBD telemetry flows through a
Redis hot path and a TimescaleDB cold path; manuals/TSBs/mechanic logs live in
Qdrant. Two LangGraph agents — **Mater** (driver, voice) and **Host** (owner,
chat) — reach all of it through a single Fast-MCP tool layer backed by a local
Ollama LLM.

# High Level Architecture

```mermaid
flowchart TB

    feed["live-car-api (Vercel)<br/>WebSocket • grouped telemetry @2Hz"]

    %% ── Ingestion Layer ──
    subgraph INGESTION["Ingestion"]
        bridge["telemetry-bridge<br/>ws_adapter.py<br/>grouped → flat TelemetryFrame"]
        api["FastAPI /live-car-data<br/>writer.py"]
        flusher["Flusher<br/>write-behind • 1s batches"]
    end

    knowledge["Knowledge ingest CLI<br/>tools/ingest_knowledge.py"]

    %% ── Data Stores ──
    subgraph STORES["Data Stores"]
        redis["Redis — Hot Path<br/>live snapshot • per-signal cache<br/>alerts • MIL • maintenance • location"]
        tsdb["TimescaleDB — Cold Path<br/>car_telemetry hypertable<br/>1m / 5m / 1h aggregates • trips"]
        qdrant["Qdrant — Knowledge Path<br/>manuals • TSBs • mechanic logs"]
    end

    %% ── MCP Layer ──
    subgraph MCP["Fast-MCP Server — 14 tools"]
        tools["get_latest_snapshot • get_signal_latest<br/>get_signal_timeline • check_active_alerts<br/>get_location • predict_anomalies<br/>search_knowledge • get_dtc_info<br/>get_maintenance_schedule • get_trip_summary • …"]
    end

    %% ── Agent Gateway ──
    subgraph AGENTS["Agent Gateway :8100"]
        mater["Mater Agent<br/>driver • voice"]
        host["Host Agent<br/>owner • chat"]
        reads["Dashboard read-throughs<br/>/api/snapshot • /api/alerts"]
    end

    ollama["Ollama<br/>gemma4:e4b"]

    %% ── Interfaces ──
    subgraph UI["Frontend — Next.js"]
        driver["/driver<br/>gauges + Mater voice (Web Speech)"]
        hostui["/host<br/>chat"]
    end

    %% ── Flows ──
    feed --> bridge --> api
    api -->|hot-path write| redis
    api -->|enqueue rows| flusher
    flusher -->|COPY batch| tsdb
    knowledge --> qdrant

    redis --> tools
    tsdb --> tools
    qdrant --> tools

    tools --> mater
    tools --> host
    mater --> ollama
    host --> ollama
    reads --> redis

    driver -->|"poll (1s)"| reads
    driver -->|"voice → /api/chat"| mater
    hostui -->|"chat → /api/chat"| host
    mater -->|spoken reply| driver
    host -->|chat reply| hostui

%% ── Styling ──
    classDef src fill:#ede9fe,stroke:#7c3aed,stroke-width:2px,color:#333333
    classDef ingestion fill:#e6f3ff,stroke:#4a90d9,stroke-width:2px,color:#1e3a8a
    classDef store fill:#f0f4f8,stroke:#5b6f82,stroke-width:2px,color:#333333
    classDef mcp fill:#fff3e0,stroke:#f57c00,stroke-width:2px,color:#854d0e
    classDef agent fill:#e8f5e9,stroke:#388e3c,stroke-width:2px,color:#14532d
    classDef ui fill:#fce4ec,stroke:#d81b60,stroke-width:2px,color:#831843

    class feed,knowledge src
    class bridge,api,flusher ingestion
    class redis,tsdb,qdrant store
    class tools mcp
    class mater,host,reads agent
    class driver,hostui ui
```

## Layout

```text
/db/init.sql       TimescaleDB schema: hypertable, continuous aggregates,
                   compression + retention, supplementary tables, signal registry
/backend
  /common          config, store clients, Redis key schema, models, rules, Qdrant
  /ingestion       FastAPI `/live-car-data` + write-behind flusher  (port 8000)
  /mcp_server      Fast-MCP server with the 13 tools                (port 8765)
  /agent           LangGraph Mater + Host agents + HTTP gateway      (port 8100)
  /tools           knowledge-ingestion CLI + telemetry simulator
/frontend          Next.js dashboard (gauges) + chat                (port 3000)
docker-compose.yml all services + Redis / TimescaleDB / Qdrant / Ollama
```

## Quick start

```bash
docker compose up -d --build          # bring up everything

# Pull the LLM into Ollama (one time)
docker exec mater_ollama ollama pull gemma4:e4b

```

Then open the dashboard at <http://localhost:3000>. Gauges update once per
second from the Redis snapshot; the chat panel talks to the Host/Mater agents.

### Ports

| Service     | URL                                 | Purpose                |
| ----------- | ----------------------------------- | ---------------------- |
| Ingestion   | http://localhost:8000/live-car-data | Telemetry write path   |
| MCP server  | http://localhost:8765/mcp           | 13-tool layer          |
| Agent API   | http://localhost:8100/api/chat      | Chat + dashboard reads |
| Frontend    | http://localhost:3000               | Dashboard + chat       |
| TimescaleDB | localhost:5432                      | Cold path              |
| Qdrant      | http://localhost:6333               | Knowledge path         |
| Redis       | localhost:6379                      | Hot path               |
| Ollama      | http://localhost:11434              | LLM engine             |

## Ingest knowledge (RAG)

```bash
python backend/tools/ingest_knowledge.py \
    --car-id acc001 --model Accord --source manual --system engine \
    path/to/accord_manual.txt
```

## Local dev (stores in Docker, backend on host)

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
docker compose up -d timescaledb redis qdrant ollama   # stores only

uvicorn ingestion.app:app --reload --port 8000   # terminal 1
python -m mcp_server.server                       # terminal 2
uvicorn agent.api:app --reload --port 8100        # terminal 3
```

## Notes / scope

* **Audio** (whisper.cpp ASR, VoXtream2 TTS, wake-word) is device/native and is
  not bundled here — the Mater agent exposes a text `/api/chat` surface that a
  voice front-end would wrap.
* `gemma4:e4b` is the default Ollama tag; set `LLM_MODEL` to the exact
  gemma4:e4b build you run.
* The backend is one image with multiple entrypoints (ingestion / mcp / agent),
  keeping the shared `common` code DRY.
