'''Application entry point and graph initialization for Trip Planner.'''

from __future__ import annotations

from typing import Optional

from langchain_core.messages import AIMessage, HumanMessage
from langchain_nvidia_ai_endpoints import ChatNVIDIA
from langgraph.graph.state import CompiledStateGraph

from src.config import settings
from src.graph.graph import build_graph

_graph: Optional[CompiledStateGraph] = None


def get_graph() -> CompiledStateGraph:
    '''Initialize the NVIDIA chat model and build the Trip Planner graph once.

    Returns:
        CompiledStateGraph: The cached compiled LangGraph workflow.

    Raises:
        ValueError: If ``API_KEY`` is missing or empty.
    '''
    global _graph
    if _graph is not None:
        return _graph

    if not settings.NVIDIA_API_KEY:
        raise ValueError("api key is not set. Please configure your api_key in your .env")

    llm = ChatNVIDIA(
        model=settings.LLM_MODEL,
        api_key=settings.NVIDIA_API_KEY,
    )
    _graph = build_graph(model=llm)
    return _graph


if __name__ == "__main__":
    graph = get_graph()
    messages = []  # this list is the session memory

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not user_input:
            continue
        if user_input.lower() in ("exit", "quit"):
            break

        result = graph.invoke({"messages": messages + [HumanMessage(content=user_input)]})
        messages = result["messages"]

        print("Agent:", messages[-1].content)