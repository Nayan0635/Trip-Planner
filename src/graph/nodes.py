'''Graph nodes for the Trip Planner workflow.'''
from __future__ import annotations
from typing import Any, Callable, Optional, Sequence

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage, SystemMessage
from langchain_core.runnables import RunnableConfig

from src.graph.prompts import SYSTEM_PROMPT
from src.graph.state import GraphState


def _bind_tools_if_supported(llm: Any, tools: Optional[Sequence[Any]]) -> Any:
    '''Bind tools to the model if the model supports `bind_tools`.'''
    if not tools:
        return llm
    bind_tools = getattr(llm, "bind_tools", None)
    if bind_tools is None:
        return llm
    try:
        return bind_tools(tools)
    except NotImplementedError:
        return llm

def create_assistant_node(
    model: BaseChatModel,
    tools: Optional[Sequence[Any]] = None,
) -> Callable[[GraphState, Optional[RunnableConfig]], dict[str, list[BaseMessage]]]:
    '''Create the assistant/LLM node function.

    Args:
        model: Pre-initialized chat model to use for this node.
        tools: Sequence of tools to bind to the model, if any.

    Returns:
        Callable node function for LangGraph.
    '''
    bound_model = _bind_tools_if_supported(model, tools)

    def assistant(
        state: GraphState,
        config: Optional[RunnableConfig] = None,
    ) -> dict[str, list[BaseMessage]]:
        messages = state.get("messages", [])
        if not messages:
            raise ValueError(
                "Graph state contains no messages. At least one user message is required."
            )

        prompt_messages: list[BaseMessage] = []
        if not isinstance(messages[0], SystemMessage):
            prompt_messages.append(SystemMessage(content=SYSTEM_PROMPT))
        prompt_messages.extend(messages)

        response = bound_model.invoke(prompt_messages, config=config)
        return {"messages": [response]}

    return assistant