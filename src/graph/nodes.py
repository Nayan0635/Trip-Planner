"""Graph nodes and model initialization for the Trip Planner workflow."""

from __future__ import annotations

from typing import Any, Callable, Optional, Sequence

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage, SystemMessage
from langchain_core.runnables import RunnableConfig

from src.config import settings
from src.graph.prompts import SYSTEM_PROMPT
from src.graph.state import GraphState


def get_llm(
    model: Optional[str] = None,
    api_key: Optional[str] = None,
) -> BaseChatModel:
    """Initialize and return the configured chat model.

    Uses settings from `src.config.settings` for provider and model selection.
    Currently configured for NVIDIA endpoints via `ChatNVIDIA`.

    Args:
        model: Optional model name override.
        api_key: Optional API key override.

    Returns:
        BaseChatModel: Configured ChatNVIDIA instance.

    Raises:
        ValueError: If provider is unsupported or NVIDIA_API_KEY is missing.
        ImportError: If langchain_nvidia_ai_endpoints is not installed.
    """
    if settings.LLM_PROVIDER != "nvidia":
        raise ValueError(
            f"Unsupported LLM provider '{settings.LLM_PROVIDER}'. Expected 'nvidia'."
        )

    key = api_key or settings.NVIDIA_API_KEY
    if not key:
        raise ValueError(
            "NVIDIA_API_KEY is not configured. Please set the NVIDIA_API_KEY "
            "environment variable in your environment or .env file."
        )

    try:
        from langchain_nvidia_ai_endpoints import ChatNVIDIA
    except ImportError as exc:
        raise ImportError(
            "The 'langchain_nvidia_ai_endpoints' package is required for the NVIDIA provider. "
            "Please ensure it is installed."
        ) from exc

    model_name = model or settings.LLM_MODEL
    return ChatNVIDIA(model=model_name, nvidia_api_key=key)


def _bind_tools_if_supported(llm: Any, tools: Optional[Sequence[Any]]) -> Any:
    """Bind tools to the model if the model supports `bind_tools`."""
    if tools and hasattr(llm, "bind_tools"):
        try:
            return llm.bind_tools(tools)
        except (NotImplementedError, AttributeError):
            return llm
    return llm


def create_assistant_node(
    model: Optional[BaseChatModel] = None,
    tools: Optional[Sequence[Any]] = None,
) -> Callable[[GraphState, Optional[RunnableConfig]], dict[str, list[BaseMessage]]]:
    """Create the assistant/LLM node function.

    Args:
        model: Pre-initialized chat model or injected test model. If None,
            the configured LLM will be initialized lazily on first invocation.
        tools: Sequence of tools to bind to the model. If None and model is None,
            the default travel tools from `src.graph.graph.TOOLS` are used.

    Returns:
        Callable node function for LangGraph.
    """
    # If a model was injected and tools were passed, bind them upfront
    bound_model = _bind_tools_if_supported(model, tools) if model is not None else None

    def assistant(
        state: GraphState,
        config: Optional[RunnableConfig] = None,
    ) -> dict[str, list[BaseMessage]]:
        messages = state.get("messages", [])
        if not messages:
            raise ValueError(
                "Graph state contains no messages. At least one user message is required."
            )

        nonlocal bound_model
        if bound_model is None:
            from src.graph.graph import TOOLS

            llm = get_llm()
            tool_set = tools if tools is not None else TOOLS
            bound_model = _bind_tools_if_supported(llm, tool_set)

        # Apply system prompt if not already present at the start of conversation
        prompt_messages: list[BaseMessage] = []
        if not any(isinstance(m, SystemMessage) for m in messages):
            prompt_messages.append(SystemMessage(content=SYSTEM_PROMPT))
        prompt_messages.extend(messages)

        response = bound_model.invoke(prompt_messages, config=config)
        return {"messages": [response]}

    return assistant


# Default assistant node using lazy initialization with default configuration
assistant_node = create_assistant_node()
