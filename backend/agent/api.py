"""HTTP gateway for the frontend: chat with either agent + live snapshot reads.

Run with: ``uvicorn agent.api:app``. Depends on the MCP server (tools) and
Ollama (model) being reachable.
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from langchain_core.messages import HumanMessage
from pydantic import BaseModel

from mcp_server import queries

from .graph import get_agent

app = FastAPI(title="Mater Agent Gateway", version="0.1.0")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)


class ChatRequest(BaseModel):
    message: str
    agent: str = "host"          # "mater" | "host"
    car_id: str | None = None


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.post("/api/chat")
async def chat(req: ChatRequest) -> dict:
    agent = await get_agent("mater" if req.agent == "mater" else "host")
    context = f"(active car_id: {req.car_id}) " if req.car_id else ""
    result = await agent.ainvoke(
        {"messages": [HumanMessage(content=context + req.message)]}
    )
    reply = result["messages"][-1].content
    return {"reply": reply, "agent": req.agent}


# Lightweight read-throughs for the dashboard (no LLM in the loop).
@app.get("/api/snapshot/{car_id}")
async def snapshot(car_id: str) -> dict:
    return await queries.latest_snapshot(car_id) or {"car_id": car_id, "signals": {}}


@app.get("/api/alerts/{car_id}")
async def alerts(car_id: str) -> list[dict]:
    return await queries.active_alerts(car_id)


@app.get("/api/cars")
async def cars() -> list[dict]:
    return await queries.list_cars()
