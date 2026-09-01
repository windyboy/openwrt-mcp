#!/usr/bin/env python3
"""
OpenWRT MCP Server
Model Context Protocol server for OpenWRT router management and diagnostics.

Transport: MCP over stdin/stdout only. The MCP client owns the process lifecycle.
"""

import asyncio
import logging
import os
import sys
from typing import Any

from fastmcp import FastMCP

from openwrt_mcp.observability import get_request_id
from openwrt_mcp.sanitizer import sanitize_log_line
from openwrt_mcp.tools.constants import LOG_LEVEL, OPENWRT_SSH_KEY
from openwrt_mcp.tools.registration import register_openwrt_tools

# =============================================================================
# LOGGING CONFIGURATION
# =============================================================================


class RequestIdFilter(logging.Filter):
    """Inject the current request_id into every log record (Template 4a)."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = get_request_id()
        return True


class SanitizingFormatter(logging.Formatter):
    """Redact credentials and IP addresses from every formatted log line."""

    def format(self, record: logging.LogRecord) -> str:
        return sanitize_log_line(super().format(record))


def setup_logging() -> None:
    """Configure stderr logging with request-id context and secret redaction.

    Sanitization enforced at the logging infrastructure level cannot be
    bypassed by a developer forgetting to call sanitize_log_line() manually.
    """
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(
        SanitizingFormatter("%(asctime)s [%(levelname)s] [%(request_id)s] %(name)s: %(message)s")
    )
    handler.addFilter(RequestIdFilter())
    root = logging.getLogger()
    root.addHandler(handler)
    root.setLevel(getattr(logging, LOG_LEVEL.upper(), logging.INFO))


setup_logging()
logger = logging.getLogger("openwrt-mcp")

# =============================================================================
# CONFIGURATION
# =============================================================================

if not os.path.exists(OPENWRT_SSH_KEY):
    logger.warning("SSH key not found at %s — OpenWRT features will be disabled", OPENWRT_SSH_KEY)

# =============================================================================
# INITIALIZE MCP SERVER
# =============================================================================

mcp = FastMCP("OpenWRT-Observer")

# =============================================================================
# REGISTER ALL TOOLS
# =============================================================================

register_openwrt_tools(mcp)

# =============================================================================
# TOOL HELPERS
# =============================================================================


_tool_cache: dict[str, Any] = {}


def get_all_tools() -> dict[str, Any]:
    """Return a dictionary of all registered tools.

    Supports FastMCP 2.x (_tool_manager._tools, _tools) and 3.x (list_tools async).
    Lazy-populates the internal cache on first call for FastMCP 3.x.
    """
    global _tool_cache
    if hasattr(mcp, "_tool_manager") and hasattr(mcp._tool_manager, "_tools"):
        return dict(mcp._tool_manager._tools)
    if hasattr(mcp, "_tools"):
        return dict(mcp._tools)
    if hasattr(mcp, "list_tools") and not _tool_cache:
        _tool_cache = _list_tools_sync()
    return _tool_cache


def _list_tools_sync() -> dict[str, Any]:
    """Call mcp.list_tools() synchronously. Thread-safe."""
    list_tools_method = getattr(mcp, "list_tools", None)
    if list_tools_method is None:
        return {}
    loop = asyncio.new_event_loop()
    tools_result: list[Any] = loop.run_until_complete(list_tools_method())
    loop.close()
    cache: dict[str, Any] = {}
    for t in tools_result:
        name = getattr(t, "name", None)
        if name:
            cache[name] = t
    return cache


def get_tool(name: str) -> Any | None:
    """Return tool by name if available."""
    return get_all_tools().get(name)


def get_tool_manifest(tool_name: str) -> dict[str, Any] | None:
    """Return the manifest for a tool if available."""
    tool = get_tool(tool_name)
    if tool is not None and hasattr(tool, "__manifest__"):
        manifest: dict[str, Any] = tool.__manifest__
        return manifest
    return None


def get_tool_count() -> int:
    """Return the number of registered tools."""
    return len(get_all_tools())


tool_count = get_tool_count()


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================


def main() -> None:
    """Main entry point for the OpenWRT MCP server (stdio only)."""
    from openwrt_mcp.tools.constants import OPENWRT_HOST, OPENWRT_PORT

    logger.info("Starting MCP stdio transport")
    logger.info("OpenWRT Host: %s:%s", OPENWRT_HOST, OPENWRT_PORT)
    logger.info("Registered tools: %s", tool_count)
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
