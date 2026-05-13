"""
core/brain.py — LLM orchestration via Groq API (free tier).

Uses Llama 3.3 70B on Groq — fast inference, free, supports tool use.
The brain takes text in and returns text out; voice is just an adapter on top.

Groq API is OpenAI-compatible, so tool format follows OpenAI conventions
(different from Anthropic's format — conversion handled in _to_groq_tools).
"""

from __future__ import annotations

import json
import os
from typing import Any

from groq import Groq, APIConnectionError, APIStatusError, RateLimitError

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are Jarvis, a personal AI agent for Prathamesh — a CS student.

You are not just a voice assistant. You are a fully capable agent that can:
- Control the computer (see screen, click, type, use any app)
- Browse the web and extract information
- Manage files, emails, and calendar
- Execute multi-step tasks autonomously
- Remember context across sessions

RESPONSE RULES (spoken aloud):
- Keep responses concise — 1-3 sentences max
- No markdown, no bullet points, no headers
- Calm, professional tone — not chirpy, not robotic
- After completing actions, briefly confirm what was done

TOOL USE RULES:
- Always use tools to take real actions — never just describe what you would do
- For multi-step tasks: plan first, then execute step by step using tools
- Use read_screen before interacting with UI to understand current state
- Use recall_memory at the start of conversations referencing past context
- Use remember_fact when user shares preferences or important information

CONFIRMATION REQUIRED before:
- Sending emails or messages
- Deleting files or data
- Creating calendar events
- Closing applications
- Any action that cannot be undone
"""


# ---------------------------------------------------------------------------
# Brain
# ---------------------------------------------------------------------------

class Brain:
    """Manages conversation state and calls Groq (Llama 3.3) with tool use."""

    def __init__(self, tools: list[dict[str, Any]], tool_handlers: dict[str, Any]) -> None:
        """
        Args:
            tools:         Tool schemas in Anthropic format (name, description, input_schema).
                           Brain converts them to Groq/OpenAI format internally.
            tool_handlers: Mapping of tool name → callable(input_dict) → str.
        """
        self._client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        self._model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
        self._groq_tools = _to_groq_tools(tools)
        self._tool_handlers = tool_handlers
        self._history: list[dict[str, Any]] = [
            {"role": "system", "content": SYSTEM_PROMPT}
        ]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def think(self, user_input: str) -> str:
        """
        Process a user message and return Jarvis's response.

        Handles multi-turn tool-call loops automatically.

        Args:
            user_input: Transcribed or typed user message.

        Returns:
            Final assistant response as plain text.
        """
        self._history.append({"role": "user", "content": user_input})

        while True:
            for attempt in range(3):
                try:
                    response = self._client.chat.completions.create(
                        model=self._model,
                        messages=self._history,
                        tools=self._groq_tools if self._groq_tools else None,
                        tool_choice="auto" if self._groq_tools else None,
                        max_tokens=1024,
                        temperature=0.7,
                    )
                    break  # success
                except RateLimitError:
                    if attempt < 2:
                        import time as _time
                        _time.sleep(2 ** attempt)   # 1s, 2s backoff
                        continue
                    return "I'm being rate limited. Please wait a moment and try again."
                except APIConnectionError:
                    return "I couldn't reach the server. Please check your internet connection."
                except APIStatusError as exc:
                    if exc.status_code == 400 and attempt < 2:
                        import time as _time
                        _time.sleep(1)
                        continue
                    return f"Sorry, I had trouble thinking just now. ({exc.status_code})"
            else:
                return "I'm having trouble connecting to the server right now."

            message = response.choices[0].message
            finish_reason = response.choices[0].finish_reason

            if finish_reason == "stop":
                # Plain text response — append and return
                self._history.append({"role": "assistant", "content": message.content or ""})
                return (message.content or "").strip()

            if finish_reason == "tool_calls" and message.tool_calls:
                # Append assistant message with tool_calls in clean Groq format
                self._history.append({
                    "role": "assistant",
                    "content": message.content or "",
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            },
                        }
                        for tc in message.tool_calls
                    ],
                })
                # Execute every tool and append results
                for tool_call in message.tool_calls:
                    result = self._run_tool(tool_call)
                    self._history.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": result,
                    })
                # Loop — model reads tool results and gives final response
            else:
                return (message.content or "I had trouble processing that.").strip()

    def reset_history(self) -> None:
        """Clear session history but keep the system prompt."""
        self._history = [{"role": "system", "content": SYSTEM_PROMPT}]

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _run_tool(self, tool_call: Any) -> str:
        """Execute a single tool call and return the string result."""
        name = tool_call.function.name
        try:
            args = json.loads(tool_call.function.arguments)
        except json.JSONDecodeError:
            args = {}

        handler = self._tool_handlers.get(name)
        if handler is None:
            result = f"Error: tool '{name}' is not registered."
        else:
            try:
                result = handler(args)
            except Exception as exc:
                result = f"Error executing {name}: {exc}"

        print(f"[Brain] Tool '{name}' -> {result!r}")
        return result


# ---------------------------------------------------------------------------
# Format conversion: Anthropic schema → Groq/OpenAI schema
# ---------------------------------------------------------------------------

def _to_groq_tools(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Convert Anthropic-style tool schemas to OpenAI/Groq format.

    Anthropic:  { name, description, input_schema: { type, properties, required } }
    OpenAI:     { type: "function", function: { name, description, parameters: { ... } } }
    """
    groq_tools = []
    for t in tools:
        groq_tools.append({
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t.get("description", ""),
                "parameters": t.get("input_schema", {"type": "object", "properties": {}}),
            },
        })
    return groq_tools
