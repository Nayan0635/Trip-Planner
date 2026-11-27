'''Streamlit chat UI for the AI Trip Planner.'''

from __future__ import annotations

import logging
import os

import streamlit as st
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from main import get_graph
from src.config import settings

logger = logging.getLogger(__name__)

st.set_page_config(page_title="AI Trip Planner", page_icon="✈️", layout="wide")


@st.cache_resource
def load_graph():
    '''Cache the compiled LangGraph workflow across the Streamlit server session.'''
    return get_graph()


def _key_status(env_var: str, settings_val: str | None) -> str:
    '''Return a non-sensitive configuration status label for an API key.'''
    return "✅ Configured" if (os.environ.get(env_var) or settings_val) else "⚠️ Missing"


# Initialize conversation history
if "messages" not in st.session_state:
    st.session_state["messages"] = []

# Sidebar
with st.sidebar:
    st.title("✈️ AI Trip Planner")
    st.caption("Plan trips with AI recommendations and live travel data.")

    st.subheader("Capabilities")
    st.markdown(
        "- **Attractions** — Discover nearby landmarks and points of interest\n"
        "- **Weather** — Check current weather conditions at destinations\n"
        "- **Currency** — Convert amounts using live exchange rates\n"
        "- **Expense Organizer** — Group estimated costs by category\n"
        "- **Expense Total** — Calculate total estimated trip cost"
    )

    st.subheader("API Status")
    st.markdown(
        f"- `NVIDIA_API_KEY`: {_key_status('NVIDIA_API_KEY', settings.NVIDIA_API_KEY)}\n"
        f"- `OPENTRIPMAP_API_KEY`: {_key_status('OPENTRIPMAP_API_KEY', settings.OPENTRIPMAP_API_KEY)}\n"
        f"- `OPENWEATHERMAP_API_KEY`: {_key_status('OPENWEATHERMAP_API_KEY', settings.OPENWEATHERMAP_API_KEY)}"
    )

    if st.button("Clear chat", use_container_width=True):
        st.session_state["messages"] = []
        st.rerun()

# Main chat area
st.title("AI Trip Planner")

if not st.session_state["messages"]:
    with st.chat_message("assistant"):
        st.markdown(
            "Welcome! Tell me where you'd like to go, your travel preferences, "
            "or ask me about attractions, current weather, currency conversions, "
            "and trip expenses."
        )
else:
    for msg in st.session_state["messages"]:
        if isinstance(msg, (SystemMessage, ToolMessage)):
            continue
        if isinstance(msg, AIMessage) and getattr(msg, "tool_calls", None):
            continue
        if isinstance(msg, HumanMessage):
            with st.chat_message("user"):
                st.markdown(msg.content)
        elif isinstance(msg, AIMessage):
            with st.chat_message("assistant"):
                st.markdown(msg.content)

if prompt := st.chat_input("Ask me anything about your trip..."):
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        try:
            graph = load_graph()
            with st.spinner("Planning your trip..."):
                result = graph.invoke(
                    {"messages": st.session_state["messages"] + [HumanMessage(content=prompt)]}
                )
            st.session_state["messages"] = result["messages"]
            st.markdown(result["messages"][-1].content)
        except ValueError as err:
            st.error(str(err))
        except Exception:
            logger.exception("Error during Trip Planner graph invocation.")
            st.error("Something went wrong. Please try again.")