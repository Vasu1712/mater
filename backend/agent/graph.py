"""LangGraph ReAct agents for Mater (driver) and Host (owner).

Both agents share the Fast-MCP tool layer and the local Ollama model
(gemma4:e4b). Tools are loaded over MCP so the agents stay decoupled from the
data stores.
"""
from __future__ import annotations

from functools import lru_cache

from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_ollama import ChatOllama
from langgraph.prebuilt import create_react_agent

from common.config import settings

from .prompts import HOST_SYSTEM, MATER_SYSTEM

# Tools 1-8 belong to Mater; 9-13 to Host. We filter by name after loading.
_MATER_TOOLS = {
    "get_latest_snapshot", "get_signal_latest", "get_signal_timeline",
    "get_trip_summary", "search_knowledge", "check_active_alerts",
    "predict_anomalies", "get_dtc_info", "get_location",
}
_HOST_TOOLS = {
    "get_cars", "get_trip_history", "get_weekly_report",
    "get_maintenance_schedule", "acknowledge_alert", "get_location",
    # Host can also read history/knowledge:
    "get_signal_timeline", "get_trip_summary", "search_knowledge",
}


def _llm() -> ChatOllama:
    return ChatOllama(model=settings.LLM_MODEL, base_url=settings.OLLAMA_URL, temperature=0.2)


async def _load_tools() -> list:
    client = MultiServerMCPClient(
        {"mater": {"url": settings.MCP_URL, "transport": "streamable_http"}}
    )
    return await client.get_tools()


async def build_mater():
    tools = [t for t in await _load_tools() if t.name in _MATER_TOOLS]
    return create_react_agent(_llm(), tools, prompt=MATER_SYSTEM)


async def build_host():
    tools = [t for t in await _load_tools() if t.name in _HOST_TOOLS]
    return create_react_agent(_llm(), tools, prompt=HOST_SYSTEM)


@lru_cache(maxsize=2)
def _cache():  # noqa: D401 - simple memo dict
    return {}


async def get_agent(kind: str):
    """Return (and memoize) the requested agent. kind in {"mater","host"}."""
    cache = _cache()
    if kind not in cache:
        cache[kind] = await (build_mater() if kind == "mater" else build_host())
    return cache[kind]
