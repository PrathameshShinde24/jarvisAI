"""
core/memory.py — Long-term vector memory via ChromaDB + sentence-transformers.

Provides two Claude tools:
  remember_fact(fact: str)     → stores a fact in the vector DB
  recall_memory(query: str)    → retrieves the most relevant stored facts
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import chromadb
from chromadb.utils import embedding_functions

# ---------------------------------------------------------------------------
# Storage location (git-ignored via data/ entry in .gitignore)
# ---------------------------------------------------------------------------

DATA_DIR = Path(__file__).parent.parent / "data" / "memory"

# ---------------------------------------------------------------------------
# Tool schemas (registered with the Brain in Phase 6)
# ---------------------------------------------------------------------------

TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "name": "remember_fact",
        "description": "Store a fact or preference that the user wants Jarvis to remember across sessions.",
        "input_schema": {
            "type": "object",
            "properties": {
                "fact": {
                    "type": "string",
                    "description": "The fact or preference to remember, stated as a plain sentence.",
                }
            },
            "required": ["fact"],
        },
    },
    {
        "name": "recall_memory",
        "description": "Retrieve stored facts relevant to the given query. Call at the start of conversations that reference past context.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Natural-language query to search stored memories.",
                }
            },
            "required": ["query"],
        },
    },
]


# ---------------------------------------------------------------------------
# Memory store
# ---------------------------------------------------------------------------

class MemoryStore:
    """Wraps ChromaDB for persistent fact storage and retrieval."""

    def __init__(self) -> None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(path=str(DATA_DIR))
        self._ef = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2"
        )
        self._collection = self._client.get_or_create_collection(
            name="jarvis_memory",
            embedding_function=self._ef,
        )

    # ------------------------------------------------------------------
    # Tool handlers (called by Brain._execute_tools)
    # ------------------------------------------------------------------

    def remember_fact(self, inputs: dict[str, str]) -> str:
        """Store a fact. Returns a confirmation string."""
        fact = inputs["fact"]
        doc_id = f"fact_{self._collection.count()}_{hash(fact) & 0xFFFFFF}"
        self._collection.add(documents=[fact], ids=[doc_id])
        return f"Got it, I'll remember that: {fact}"

    def recall_memory(self, inputs: dict[str, str]) -> str:
        """Retrieve up to 5 relevant facts. Returns them as a newline-joined string."""
        query = inputs["query"]
        if self._collection.count() == 0:
            return "No memories stored yet."
        results = self._collection.query(query_texts=[query], n_results=min(5, self._collection.count()))
        docs = results.get("documents", [[]])[0]
        if not docs:
            return "No relevant memories found."
        return "\n".join(f"- {d}" for d in docs)
