"""
tools — Tool implementations grouped by capability.

Each module exposes:
  TOOL_SCHEMAS  : list[dict]  — Claude tool schema definitions
  TOOL_HANDLERS : dict[str, callable]  — name → handler function

server.py collects these and registers them with the Brain in one loop.
"""

from tools.system       import TOOL_SCHEMAS as SYSTEM_SCHEMAS,       TOOL_HANDLERS as SYSTEM_HANDLERS
from tools.web          import TOOL_SCHEMAS as WEB_SCHEMAS,          TOOL_HANDLERS as WEB_HANDLERS
from tools.productivity import TOOL_SCHEMAS as PRODUCTIVITY_SCHEMAS, TOOL_HANDLERS as PRODUCTIVITY_HANDLERS
from tools.computer     import TOOL_SCHEMAS as COMPUTER_SCHEMAS,     TOOL_HANDLERS as COMPUTER_HANDLERS
from tools.files        import TOOL_SCHEMAS as FILES_SCHEMAS,        TOOL_HANDLERS as FILES_HANDLERS
from core.memory        import TOOL_SCHEMAS as MEMORY_SCHEMAS

# MemoryStore is instantiated once here so both handlers share the same DB
from core.memory import MemoryStore
_memory = MemoryStore()
MEMORY_HANDLERS = {
    "remember_fact": _memory.remember_fact,
    "recall_memory": _memory.recall_memory,
}

ALL_SCHEMAS  = (SYSTEM_SCHEMAS + WEB_SCHEMAS + PRODUCTIVITY_SCHEMAS +
                COMPUTER_SCHEMAS + FILES_SCHEMAS + MEMORY_SCHEMAS)
ALL_HANDLERS = {**SYSTEM_HANDLERS, **WEB_HANDLERS, **PRODUCTIVITY_HANDLERS,
                **COMPUTER_HANDLERS, **FILES_HANDLERS, **MEMORY_HANDLERS}
