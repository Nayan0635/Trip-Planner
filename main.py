"""Application entry point and graph initialization for Trip Planner."""

from __future__ import annotations

from typing import Optional

from langchain_core.messages import AIMessage, HumanMessage
from langchain_nvidia_ai_endpoints import ChatNVIDIA
from langgraph.graph.state import CompiledStateGraph

from src.config import settings
from src.graph.graph import build_graph

_graph: Optional[CompiledStateGraph] = None


def get_graph() -> CompiledStateGraph:
    """Initialize the NVIDIA chat model and build the Trip Planner graph once.

    Returns:
        CompiledStateGraph: The cached compiled LangGraph workflow.

    Raises:
        ValueError: If ``NVIDIA_API_KEY`` is missing or empty.
    """
    global _graph
    if _graph is not None:
        return _graph

    if not settings.NVIDIA_API_KEY:
        raise ValueError(
            "NVIDIA_API_KEY is not set. Please configure NVIDIA_API_KEY in your "
            "environment or .env file before running the Trip Planner."
        )

    llm = ChatNVIDIA(
        model=settings.LLM_MODEL,
        nvidia_api_key=settings.NVIDIA_API_KEY,
    )
    _graph = build_graph(model=llm)
    return _graph


if __name__ == "__main__":
    graph = get_graph()
    result = graph.invoke(
        {
            "messages": [
                HumanMessage(content="Suggest 3 great weekend destinations in Europe.")
            ]
        }
    )
    final_response = next(
        (
            m
            for m in reversed(result["messages"])
            if isinstance(m, AIMessage) and not getattr(m, "tool_calls", None)
        ),
        None,
    )
    if final_response is not None:
        print(final_response.content)
