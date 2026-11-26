'''State schema definition for the Trip Planner LangGraph workflow.'''
from __future__ import annotations

from typing import Annotated
from typing_extensions import TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

class GraphState(TypedDict):
    '''Maintains the full conversation message history across the workflow
    including user requests, assistant responses, tool calls, and tool outputs.
    The `add_messages` reducer appends new messages while supporting updates
    by message ID.
    '''
    messages: Annotated[list[BaseMessage], add_messages]