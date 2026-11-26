'''Automated tests for LangGraph implementation in src/graph/.'''
from __future__ import annotations

import sys
from pathlib import Path
# Ensure project root is on sys.path so `src` is importable
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


import os
import unittest
from typing import Any
from unittest.mock import MagicMock, patch

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from src.graph.graph import TOOLS, build_graph, route_tools
from src.graph.nodes import create_assistant_node
from src.graph.prompts import SYSTEM_PROMPT
from src.graph.state import GraphState


class MockToolCallingChatModel:
    '''A mock chat model that returns a sequence of predetermined AIMessages.
    Supports `bind_tools()` and `invoke()`.
    '''

    def __init__(self, responses: list[AIMessage]):
        self._responses = list(responses)
        self.invocations: list[list[Any]] = []

    def bind_tools(self, tools: Any, **kwargs: Any) -> MockToolCallingChatModel:
        return self

    def invoke(self, messages: list[Any], **kwargs: Any) -> AIMessage:
        self.invocations.append(messages)
        if not self._responses:
            return AIMessage(content="Default mock response.")
        return self._responses.pop(0)


class TestGraphImplementation(unittest.TestCase):
    '''Test suite covering the graph state, nodes, routing, tools, and compilation.'''

    def test_graph_construction_and_compilation(self):
        '''Verify the graph compiles and includes assistant and tools nodes.'''
        mock_model = MockToolCallingChatModel([AIMessage(content="Hello!")])
        graph = build_graph(model=mock_model)
        self.assertIsNotNone(graph)
        self.assertIn("assistant", graph.nodes)
        self.assertIn("tools", graph.nodes)

    def test_registered_tools_count_and_identities(self):
        '''Verify all 5 required tools are registered in the graph module.'''
        tool_names = [t.name for t in TOOLS]
        self.assertEqual(len(TOOLS), 5)
        self.assertIn("get_nearby_attractions", tool_names)
        self.assertIn("get_current_weather", tool_names)
        self.assertIn("convert_currency", tool_names)
        self.assertIn("organize_by_category", tool_names)
        self.assertIn("calculate_total_cost", tool_names)

    def test_user_request_terminates_without_tool_calls(self):
        '''Verify normal conversation without tool calls terminates correctly at END.'''
        mock_model = MockToolCallingChatModel([
            AIMessage(content="I recommend visiting Kyoto, Japan in the autumn.")
        ])
        graph = build_graph(model=mock_model)

        result = graph.invoke({
            "messages": [HumanMessage(content="Where should I go for autumn foliage?")]
        })

        messages = result["messages"]
        self.assertEqual(len(messages), 2)
        self.assertIsInstance(messages[0], HumanMessage)
        self.assertIsInstance(messages[1], AIMessage)
        self.assertIn("Kyoto", messages[1].content)
        # Ensure system prompt was prepended during LLM invocation
        first_call_messages = mock_model.invocations[0]
        self.assertIsInstance(first_call_messages[0], SystemMessage)
        self.assertEqual(first_call_messages[0].content, SYSTEM_PROMPT)

    @patch("requests.get")
    def test_weather_tool_execution_flow(self, mock_get: MagicMock):
        '''Verify tool calling, execution through ToolNode, and return to assistant.'''
        # Setup mock responses for OpenWeatherMap geo & weather endpoints
        geo_mock = MagicMock()
        geo_mock.status_code = 200
        geo_mock.json.return_value = [{"name": "Tokyo", "lat": 35.6762, "lon": 139.6503, "country": "JP"}]

        weather_mock = MagicMock()
        weather_mock.status_code = 200
        weather_mock.json.return_value = {
            "name": "Tokyo",
            "main": {"temp": 21.5, "feels_like": 21.0, "humidity": 55},
            "weather": [{"description": "clear sky"}],
            "wind": {"speed": 3.2},
            "sys": {"country": "JP"},
        }
        mock_get.side_effect = [geo_mock, weather_mock]

        tool_call = {
            "name": "get_current_weather",
            "args": {"location": "Tokyo", "units": "metric"},
            "id": "weather_call_1",
            "type": "tool_call",
        }

        mock_model = MockToolCallingChatModel([
            AIMessage(content="", tool_calls=[tool_call]),
            AIMessage(content="The current weather in Tokyo is 21.5°C and clear sky."),
        ])

        with patch.dict(os.environ, {"OPENWEATHERMAP_API_KEY": "test_weather_key"}):
            graph = build_graph(model=mock_model)
            result = graph.invoke({
                "messages": [HumanMessage(content="What's the weather in Tokyo?")]
            })

        messages = result["messages"]
        # HumanMessage -> AIMessage (tool call) -> ToolMessage -> AIMessage (final)
        self.assertEqual(len(messages), 4)
        self.assertIsInstance(messages[0], HumanMessage)
        self.assertIsInstance(messages[1], AIMessage)
        self.assertEqual(len(messages[1].tool_calls), 1)
        self.assertIsInstance(messages[2], ToolMessage)
        self.assertEqual(messages[2].name, "get_current_weather")
        self.assertEqual(messages[2].tool_call_id, "weather_call_1")
        self.assertIn("clear sky", messages[2].content)
        self.assertIsInstance(messages[3], AIMessage)
        self.assertIn("21.5°C", messages[3].content)

    @patch("requests.get")
    def test_currency_conversion_tool_flow(self, mock_get: MagicMock):
        '''Verify convert_currency tool execution and routing.'''
        frankfurter_mock = MagicMock()
        frankfurter_mock.status_code = 200
        frankfurter_mock.json.return_value = [
            {"quote": "EUR", "rate": 0.92, "date": "2026-11-24"}
        ]
        mock_get.return_value = frankfurter_mock

        tool_call = {
            "name": "convert_currency",
            "args": {"amount": 100.0, "source_currency": "USD", "target_currency": "EUR"},
            "id": "curr_call_1",
            "type": "tool_call",
        }

        mock_model = MockToolCallingChatModel([
            AIMessage(content="", tool_calls=[tool_call]),
            AIMessage(content="100 USD is currently 92.0 EUR (exchange rate: 0.92 on 2026-11-24)."),
        ])

        graph = build_graph(model=mock_model)
        result = graph.invoke({
            "messages": [HumanMessage(content="Convert 100 USD to EUR")]
        })

        messages = result["messages"]
        self.assertEqual(len(messages), 4)
        self.assertIsInstance(messages[2], ToolMessage)
        self.assertEqual(messages[2].name, "convert_currency")
        self.assertIn("92.0", messages[2].content)
        self.assertIn("92.0 EUR", messages[3].content)

    @patch("requests.get")
    def test_places_tool_execution_flow(self, mock_get: MagicMock):
        '''Verify get_nearby_attractions execution through the graph.'''
        geo_mock = MagicMock()
        geo_mock.status_code = 200
        geo_mock.json.return_value = {"lat": 41.9028, "lon": 12.4964}

        radius_mock = MagicMock()
        radius_mock.status_code = 200
        radius_mock.json.return_value = [
            {"name": "Colosseum", "kinds": "historic,monument", "dist": 500.0, "rate": 7, "xid": "x1"},
            {"name": "Pantheon", "kinds": "historic,temple", "dist": 1200.0, "rate": 7, "xid": "x2"},
        ]
        mock_get.side_effect = [geo_mock, radius_mock]

        tool_call = {
            "name": "get_nearby_attractions",
            "args": {"destination": "Rome", "radius": 5000, "limit": 5},
            "id": "places_call_1",
            "type": "tool_call",
        }

        mock_model = MockToolCallingChatModel([
            AIMessage(content="", tool_calls=[tool_call]),
            AIMessage(content="Popular attractions in Rome include the Colosseum and Pantheon."),
        ])

        with patch.dict(os.environ, {"OPENTRIPMAP_API_KEY": "test_trip_key"}):
            graph = build_graph(model=mock_model)
            result = graph.invoke({
                "messages": [HumanMessage(content="What attractions should I see in Rome?")]
            })

        messages = result["messages"]
        self.assertEqual(len(messages), 4)
        self.assertIsInstance(messages[2], ToolMessage)
        self.assertEqual(messages[2].name, "get_nearby_attractions")
        self.assertIn("Colosseum", messages[2].content)
        self.assertIn("Pantheon", messages[3].content)

    def test_expenses_tools_flow(self):
        '''Verify organize_by_category and calculate_total_cost tools in graph.'''
        sample_expenses = [
            {"category": "flight", "amount": 500.0},
            {"category": "lodging", "amount": 350.0},
            {"category": "food", "amount": 150.0},
        ]

        tool_calls = [
            {
                "name": "organize_by_category",
                "args": {"expenses": sample_expenses},
                "id": "exp_call_1",
                "type": "tool_call",
            },
            {
                "name": "calculate_total_cost",
                "args": {"expenses": sample_expenses},
                "id": "exp_call_2",
                "type": "tool_call",
            },
        ]

        mock_model = MockToolCallingChatModel([
            AIMessage(content="", tool_calls=tool_calls),
            AIMessage(content="Your total estimated travel cost is $1,000 across flights, lodging, and food."),
        ])

        graph = build_graph(model=mock_model)
        result = graph.invoke({
            "messages": [HumanMessage(content="Calculate my trip budget")]
        })

        messages = result["messages"]
        # HumanMessage -> AIMessage (2 calls) -> 2 ToolMessages -> AIMessage
        self.assertEqual(len(messages), 5)
        self.assertIsInstance(messages[2], ToolMessage)
        self.assertIsInstance(messages[3], ToolMessage)
        self.assertEqual(messages[2].name, "organize_by_category")
        self.assertEqual(messages[3].name, "calculate_total_cost")
        self.assertIn("1000", messages[3].content)

    def test_tool_error_handled_gracefully_without_crash(self):
        '''Verify tool execution error returns an error ToolMessage and does not crash the graph.'''
        tool_call = {
            "name": "get_current_weather",
            "args": {"location": "Paris"},
            "id": "err_call_1",
            "type": "tool_call",
        }

        mock_model = MockToolCallingChatModel([
            AIMessage(content="", tool_calls=[tool_call]),
            AIMessage(content="I could not retrieve the weather for Paris because the API key is missing."),
        ])

        # Ensure OPENWEATHERMAP_API_KEY is not set
        with patch.dict(os.environ, {}, clear=True):
            graph = build_graph(model=mock_model)
            result = graph.invoke({
                "messages": [HumanMessage(content="Weather in Paris")]
            })

        messages = result["messages"]
        self.assertEqual(len(messages), 4)
        tool_msg = messages[2]
        self.assertIsInstance(tool_msg, ToolMessage)
        self.assertEqual(tool_msg.status, "error")
        self.assertIn("OpenWeatherMap API key is required", tool_msg.content)
        self.assertIn("could not retrieve the weather", messages[3].content)

    def test_empty_messages_validation(self):
        '''Verify assistant node raises ValueError on empty message list.'''
        node = create_assistant_node(model=MockToolCallingChatModel([]))
        with self.assertRaises(ValueError) as ctx:
            node({"messages": []})
        self.assertIn("Graph state contains no messages", str(ctx.exception))

    def test_existing_system_message_is_not_duplicated(self):
        '''Verify an existing system message is passed through without another prompt.'''
        system_message = SystemMessage(content="Use concise answers.")
        user_message = HumanMessage(content="Plan a weekend in Rome.")
        model = MockToolCallingChatModel([AIMessage(content="Here is a plan.")])
        node = create_assistant_node(model=model)

        result = node({"messages": [system_message, user_message]})

        self.assertEqual(model.invocations[0], [system_message, user_message])
        self.assertEqual(result["messages"], [AIMessage(content="Here is a plan.")])

    def test_route_tools_edge(self):
        '''Verify route_tools function routes correctly.'''
        # No messages -> END
        self.assertEqual(route_tools({"messages": []}), "__end__")

        # Plain AIMessage without tool calls -> END
        self.assertEqual(
            route_tools({"messages": [AIMessage(content="Plain response")]}),
            "__end__",
        )

        # AIMessage with tool calls -> 'tools'
        tool_call = {"name": "convert_currency", "args": {}, "id": "1"}
        self.assertEqual(
            route_tools({"messages": [AIMessage(content="", tool_calls=[tool_call])]}),
            "tools",
        )

    def test_route_tools_uses_only_latest_message(self):
        '''Verify an earlier tool call does not route after a later plain response.'''
        tool_call = {"name": "convert_currency", "args": {}, "id": "1"}
        messages = [
            AIMessage(content="", tool_calls=[tool_call]),
            AIMessage(content="Done."),
        ]

        self.assertEqual(route_tools({"messages": messages}), "__end__")


if __name__ == "__main__":
    unittest.main()
