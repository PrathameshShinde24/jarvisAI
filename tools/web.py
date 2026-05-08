"""
tools/web.py — Web tools (Phase 4).

Tools implemented here:
  - web_search(query)          — DuckDuckGo HTML scrape, no API key
  - open_url(url)              — open in default browser
  - fetch_page(url)            — return readable text from a URL
  - youtube_search(query)      — open YouTube search results
"""

from __future__ import annotations

import subprocess
import webbrowser
from typing import Any
from urllib.parse import quote_plus

import httpx
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# Tool schemas
# ---------------------------------------------------------------------------

TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "name": "web_search",
        "description": "Search the web using DuckDuckGo and return a short summary of top results.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query."}
            },
            "required": ["query"],
        },
    },
    {
        "name": "open_url",
        "description": "Open a URL in the user's default browser.",
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "Full URL including https://."}
            },
            "required": ["url"],
        },
    },
    {
        "name": "fetch_page",
        "description": "Fetch the readable text content from a URL and return it.",
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "URL to fetch."}
            },
            "required": ["url"],
        },
    },
    {
        "name": "youtube_search",
        "description": "Open a YouTube search for the given query in the default browser.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "YouTube search query."}
            },
            "required": ["query"],
        },
    },
]

# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; Jarvis/1.0)"}


def web_search(inputs: dict[str, Any]) -> str:
    query = inputs["query"]
    url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
    try:
        resp = httpx.get(url, headers=HEADERS, timeout=10, follow_redirects=True)
        soup = BeautifulSoup(resp.text, "html.parser")
        results = soup.select(".result__body")[:4]
        snippets = [r.get_text(separator=" ", strip=True) for r in results]
        if not snippets:
            return "No results found."
        return " | ".join(snippets[:3])
    except Exception as exc:
        return f"Search failed: {exc}"


def open_url(inputs: dict[str, Any]) -> str:
    url = inputs["url"]
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    webbrowser.open(url)
    return f"Opened {url} in your browser."


def fetch_page(inputs: dict[str, Any]) -> str:
    url = inputs["url"]
    try:
        resp = httpx.get(url, headers=HEADERS, timeout=10, follow_redirects=True)
        soup = BeautifulSoup(resp.text, "html.parser")
        # Remove scripts and style tags
        for tag in soup(["script", "style", "nav", "footer"]):
            tag.decompose()
        text = soup.get_text(separator=" ", strip=True)
        # Truncate to keep response manageable
        return text[:3000] + ("..." if len(text) > 3000 else "")
    except Exception as exc:
        return f"Couldn't fetch page: {exc}"


def youtube_search(inputs: dict[str, Any]) -> str:
    query = inputs["query"]
    url = f"https://www.youtube.com/results?search_query={quote_plus(query)}"
    webbrowser.open(url)
    return f"Opened YouTube search for '{query}'."


# ---------------------------------------------------------------------------
# Handler registry
# ---------------------------------------------------------------------------

TOOL_HANDLERS: dict[str, Any] = {
    "web_search": web_search,
    "open_url": open_url,
    "fetch_page": fetch_page,
    "youtube_search": youtube_search,
}
