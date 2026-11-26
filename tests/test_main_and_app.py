"""Tests for main.py and app.py (Streamlit UI)."""

from __future__ import annotations

import sys
from pathlib import Path
# Ensure project root is on sys.path so `src` is importable
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import os
import unittest
from unittest.mock import MagicMock, patch

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from streamlit.testing.v1 import AppTest

import main


class TestMain(unittest.TestCase):
    """Tests for main.get_graph()."""

    def setUp(self):
        main._graph = None

    def tearDown(self):
        main._graph = None

    def test_get_graph_missing_nvidia_key_raises_value_error(self):
        with patch("src.config.settings.NVIDIA_API_KEY", None):
            with self.assertRaises(ValueError) as ctx:
                main.get_graph()
            self.assertIn("NVIDIA_API_KEY", str(ctx.exception))

    @patch("main.build_graph")
    @patch("main.ChatNVIDIA")
    def test_get_graph_initializes_once_and_caches(self, mock_chat_nvidia, mock_build_graph):
        mock_llm = MagicMock()
        mock_chat_nvidia.return_value = mock_llm
        mock_compiled = MagicMock()
        mock_build_graph.return_value = mock_compiled

        with patch("src.config.settings.NVIDIA_API_KEY", "nvapi-test-key"), patch(
            "src.config.settings.LLM_MODEL", "nvidia/test-model"
        ):
            g1 = main.get_graph()
            g2 = main.get_graph()

        self.assertIs(g1, mock_compiled)
        self.assertIs(g1, g2)
        mock_chat_nvidia.assert_called_once_with(
            model="nvidia/test-model",
            nvidia_api_key="nvapi-test-key",
        )
        mock_build_graph.assert_called_once_with(model=mock_llm)


class TestAppUI(unittest.TestCase):
    """Tests for app.py using Streamlit AppTest."""

    def setUp(self):
        import streamlit as st
        st.cache_resource.clear()

    def test_initial_render_welcome_and_sidebar(self):
        with patch.dict(os.environ, {"NVIDIA_API_KEY": "test-key"}, clear=False):
            at = AppTest.from_file("app.py").run()

        self.assertFalse(at.exception)
        # Welcome message in chat
        assistant_msgs = [m for m in at.chat_message if m.name == "assistant"]
        self.assertEqual(len(assistant_msgs), 1)
        self.assertIn("Welcome!", assistant_msgs[0].markdown[0].value)
        # Session state starts empty
        self.assertEqual(at.session_state["messages"], [])
        # Sidebar API status & capabilities
        sidebar_md = "\n".join(el.value for el in at.sidebar.markdown)
        self.assertIn("Attractions", sidebar_md)
        self.assertIn("Weather", sidebar_md)
        self.assertIn("Currency", sidebar_md)
        self.assertIn("Expense Organizer", sidebar_md)
        self.assertIn("Expense Total", sidebar_md)
        self.assertIn("NVIDIA_API_KEY", sidebar_md)
        self.assertIn("OPENTRIPMAP_API_KEY", sidebar_md)
        self.assertIn("OPENWEATHERMAP_API_KEY", sidebar_md)

    def test_chat_submission_filters_internal_messages_and_clears(self):
        fake_graph = MagicMock()
        fake_graph.invoke.side_effect = [
            {
                "messages": [
                    SystemMessage(content="internal sys"),
                    HumanMessage(content="Weather in Paris?"),
                    AIMessage(
                        content="",
                        tool_calls=[{"name": "get_current_weather", "args": {"location": "Paris"}, "id": "1"}],
                    ),
                    ToolMessage(content='{"temperature": 18}', name="get_current_weather", tool_call_id="1"),
                    AIMessage(content="It is 18°C in Paris."),
                ]
            },
            {
                "messages": [
                    SystemMessage(content="internal sys"),
                    HumanMessage(content="Weather in Paris?"),
                    AIMessage(
                        content="",
                        tool_calls=[{"name": "get_current_weather", "args": {"location": "Paris"}, "id": "1"}],
                    ),
                    ToolMessage(content='{"temperature": 18}', name="get_current_weather", tool_call_id="1"),
                    AIMessage(content="It is 18°C in Paris."),
                    HumanMessage(content="Thanks!"),
                    AIMessage(content="You're welcome!"),
                ]
            },
        ]

        with patch("main.get_graph", return_value=fake_graph):
            at = AppTest.from_file("app.py").run()
            at.chat_input[0].set_value("Weather in Paris?").run()
            self.assertFalse(at.exception)

            # Re-run to simulate st.rerun() completing
            at.run()
            self.assertFalse(at.exception)

            # Should only show 1 user message and 1 final assistant message
            user_msgs = [m for m in at.chat_message if m.name == "user"]
            assistant_msgs = [m for m in at.chat_message if m.name == "assistant"]
            self.assertEqual(len(user_msgs), 1)
            self.assertEqual(len(assistant_msgs), 1)
            self.assertEqual(assistant_msgs[0].markdown[0].value, "It is 18°C in Paris.")

            # Follow-up preserves context
            at.chat_input[0].set_value("Thanks!").run().run()
            self.assertFalse(at.exception)
            user_msgs = [m for m in at.chat_message if m.name == "user"]
            assistant_msgs = [m for m in at.chat_message if m.name == "assistant"]
            self.assertEqual(len(user_msgs), 2)
            self.assertEqual(len(assistant_msgs), 2)
            self.assertEqual(assistant_msgs[1].markdown[0].value, "You're welcome!")

            # Clear chat resets messages and shows welcome message
            clear_btn = [b for b in at.sidebar.button if b.label == "Clear chat"][0]
            clear_btn.click().run()
            self.assertEqual(at.session_state["messages"], [])
            assistant_msgs = [m for m in at.chat_message if m.name == "assistant"]
            self.assertEqual(len(assistant_msgs), 1)
            self.assertIn("Welcome!", assistant_msgs[0].markdown[0].value)

    def test_missing_api_key_shows_error_without_crash(self):
        main._graph = None
        with patch("main.get_graph", side_effect=ValueError("NVIDIA_API_KEY is not set.")):
            # Clear streamlit resource cache so mocked get_graph is invoked
            import streamlit as st
            st.cache_resource.clear()

            at = AppTest.from_file("app.py").run()
            at.chat_input[0].set_value("Plan a trip").run()

            self.assertFalse(at.exception)
            self.assertEqual(len(at.error), 1)
            self.assertIn("NVIDIA_API_KEY is not set.", at.error[0].value)

    def test_graph_invocation_error_shows_friendly_error(self):
        fake_graph = MagicMock()
        fake_graph.invoke.side_effect = RuntimeError("sensitive internal detail")

        with patch("main.get_graph", return_value=fake_graph):
            import streamlit as st
            st.cache_resource.clear()

            at = AppTest.from_file("app.py").run()
            at.chat_input[0].set_value("Plan a trip").run()

            self.assertFalse(at.exception)
            self.assertEqual(len(at.error), 1)
            self.assertEqual(at.error[0].value, "Something went wrong. Please try again.")


if __name__ == "__main__":
    unittest.main()
