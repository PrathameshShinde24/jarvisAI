"""
tools — Tool implementations grouped by capability.

Each module exposes:
  TOOL_SCHEMAS  : list[dict]  — Claude tool schema definitions
  TOOL_HANDLERS : dict[str, callable]  — name → handler function

server.py collects these and registers them with the Brain in one loop.
"""

from tools.system import TOOL_SCHEMAS as SYSTEM_SCHEMAS, TOOL_HANDLERS as SYSTEM_HANDLERS
from tools.web import TOOL_SCHEMAS as WEB_SCHEMAS, TOOL_HANDLERS as WEB_HANDLERS

ALL_SCHEMAS = SYSTEM_SCHEMAS + WEB_SCHEMAS
ALL_HANDLERS = {**SYSTEM_HANDLERS, **WEB_HANDLERS}
