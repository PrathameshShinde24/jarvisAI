"""
core/brain.py — LLM orchestration via Anthropic Claude API.

The brain takes a text input and returns a text response.
It maintains a conversation history for the current session and
dispatches Claude tool calls to registered tool handlers.

Voice is just an adapter on top — the brain only deals in text.
"""

from __future__ import annotations

import json
import os
from typing import Any

import anthropic

# System prompt — establishes identity, voice constraints, tool rules, memory awareness
SYSTEM_PROMPT = """You are Jarvis, a voice assistant for Prathamesh.

Responses are spoken aloud — keep them concise (1–3 sentences), no markdown, no bullet points, no headers.
After completing actions, briefly confirm what was done.
Match a calm, professional tone — not chirpy, not robotic.

Use available tools to perform actions; don't just describe what you would do.

At the start of conversations referencing past context, use recall_memory.
When the user shares preferences or facts to remember, use remember_fact.

Before executing any of these actions, verbally confirm the details with the user:
- Sending email
- Creating calendar events
- Closing an application by name
- Any destructive file operation
"""


class Brain:
    """Manages conversation state and calls Claude with tool use."""

    def __init__(self, tools: list[dict[str, Any]], tool_handlers: dict[str, Any]) -> None:
        """
        Args:
            tools:         List of Claude tool schema dicts (name, description, input_schema).
            tool_handlers: Mapping of tool name → callable(input_dict) → str.
        """
        self._client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        self._model = os.getenv("CLAUDE_MODEL", "claude-3-5-sonnet-20241022")
        self._tools = tools
        self._tool_handlers = tool_handlers
        self._history: list[dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def think(self, user_input: str) -> str:
        """
        Process a user message and return Jarvis's text response.

        Handles multi-turn tool-call loops automatically.

        Args:
            user_input: Transcribed or typed user message.

        Returns:
            Final assistant response as plain text.
        """
        self._history.append({"role": "user", "content": user_input})

        while True:
            response = self._client.messages.create(
                model=self._model,
                max_tokens=1024,
                system=SYSTEM_PROMPT,
                tools=self._tools,
                messages=self._history,
            )

            # Append assistant turn to history
            self._history.append({"role": "assistant", "content": response.content})

            if response.stop_reason == "end_turn":
                # Extract plain text from the response
                return self._extract_text(response.content)

            if response.stop_reason == "tool_use":
                # Execute all tool calls and feed results back
                tool_results = self._execute_tools(response.content)
                self._history.append({"role": "user", "content": tool_results})
                # Loop — Claude will process results and continue
            else:
                return "I had trouble processing that."

    def reset_history(self) -> None:
        """Clear session conversation history (e.g. after a long idle period)."""
        self._history.clear()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _execute_tools(self, content: list[Any]) -> list[dict[str, Any]]:
        """Run all tool_use blocks in a response and return result messages."""
        results = []
        for block in content:
            if block.type != "tool_use":
                continue
            handler = self._tool_handlers.get(block.name)
            if handler is None:
                result_str = f"Error: tool '{block.name}' is not registered."
            else:
                try:
                    result_str = handler(block.input)
                except Exception as exc:
                    result_str = f"Error executing {block.name}: {exc}"
            print(f"[Brain] Tool '{block.name}' → {result_str!r}")
            results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": result_str,
            })
        return results

    @staticmethod
    def _extract_text(content: list[Any]) -> str:
        """Pull plain text from an assistant content block list."""
        parts = [block.text for block in content if hasattr(block, "text")]
        return " ".join(parts).strip()
