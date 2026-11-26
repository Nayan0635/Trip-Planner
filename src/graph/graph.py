'''LangGraph workflow construction and compilation for Trip Planner.'''
from __future__ import annotations
from typing import Any, Optional, Sequence

from langchain_core.language_models import BaseChatModel
from langgraph.graph import START, END, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode

from src.graph.nodes import create_assistant_node
from src.graph.state import GraphState
from src.tools.currency import convert_currency
from src.tools.expenses import calculate_total_cost, organize_by_category
from src.tools.places import get_nearby_attractions
from src.tools.weather import get_current_weather

# Exactly the 5 existing travel tools registered for graph execution
TOOLS: list[Any] = [
    get_nearby_attractions,
    get_current_weather,
    convert_currency,
    organize_by_category,
    calculate_total_cost,
]


def route_tools(state: GraphState) -> str:
    '''Conditional routing function after the assistant node.

    Checks whether the latest assistant message contains tool calls:
    - If tool calls exist, route to the 'tools' node.
    - Otherwise, terminate execution and route to END.

    Args:
        state: Current graph state containing conversation messages.

    Returns:
        str: Next node destination ('tools' or END).
    '''
    messages = state.get("messages", [])
    if not messages:
        return END

    last_message = messages[-1]
    if hasattr(last_message, "tool_calls") and len(last_message.tool_calls) > 0:
        return "tools"
    return END


def build_graph(
    model: Optional[BaseChatModel] = None,
    tools: Optional[Sequence[Any]] = None,
) -> CompiledStateGraph:
    '''Construct and compile the Trip Planner LangGraph workflow.

    Workflow Sequence:
    1. START -> 'assistant': User request received, processed with system prompt.
    2. 'assistant' -> conditional edge (`route_tools`):
       - If tool calls are requested -> 'tools'
       - If no tool calls -> END
    3. 'tools' -> 'assistant': Tool results are returned to the assistant node to
       formulate a contextual response or make further tool calls.

    Args:
        model: Optional chat model to inject (e.g. for testing without real credentials).
            If None, the configured NVIDIA chat model will be initialized when the
            assistant node executes.
        tools: Optional sequence of tools to register. Defaults to `TOOLS`.

    Returns:
        CompiledStateGraph: The compiled executable LangGraph application.
    '''
    active_tools = list(tools) if tools is not None else list(TOOLS)

    assistant = create_assistant_node(model=model, tools=active_tools)
    tool_node = ToolNode(tools=active_tools, handle_tool_errors=True)

    builder = StateGraph(GraphState)
    builder.add_node("assistant", assistant)
    builder.add_node("tools", tool_node)

    builder.add_edge(START, "assistant")
    builder.add_conditional_edges(
        "assistant",
        route_tools,
        {"tools": "tools", END: END},
    )
    builder.add_edge("tools", "assistant")

    return builder.compile()
