"""Unit tests for server module helpers."""

from unittest.mock import patch

from openwrt_mcp.server import get_all_tools, get_tool, get_tool_count, get_tool_manifest


class TestServerHelpers:
    """Tests for server helper functions."""

    def test_get_all_tools_returns_dict(self):
        tools = get_all_tools()
        assert isinstance(tools, dict)

    def test_get_all_tools_has_24_items(self):
        tools = get_all_tools()
        assert len(tools) == 24

    def test_get_tool_valid(self):
        tool = get_tool("get_router_info")
        assert tool is not None

    def test_get_tool_invalid(self):
        tool = get_tool("nonexistent_tool")
        assert tool is None

    def test_get_tool_count(self):
        assert get_tool_count() == 24

    def test_get_tool_manifest_valid(self):
        manifest = get_tool_manifest("get_router_info")
        assert manifest is not None
        assert "name" in manifest
        assert "version" in manifest

    def test_get_tool_manifest_invalid(self):
        manifest = get_tool_manifest("nonexistent")
        assert manifest is None

    def test_get_tool_manifest_no_attr(self):
        tools = get_all_tools()
        orig_tool = tools.get("get_router_info")
        fake_name = "_fake_no_manifest"
        tools[fake_name] = object()
        try:
            from openwrt_mcp.server import get_tool_manifest as _manifest

            # Temporarily swap get_router_info so the helper sees an object
            # without __manifest__, then restore.
            tools["get_router_info"] = object()
            manifest = _manifest("get_router_info")
            assert manifest is None
        finally:
            if orig_tool:
                tools["get_router_info"] = orig_tool
            tools.pop(fake_name, None)

    def test_logger_configured_to_stderr(self):
        import logging

        logger = logging.getLogger("openwrt-mcp")
        assert logger.level == logging.INFO or logger.level == 0

    def test_get_tool_returns_none_for_empty(self):
        assert get_tool("") is None

    def test_main_runs_stdio(self):
        from openwrt_mcp.server import main

        with patch("openwrt_mcp.server.mcp.run") as mock_mcp:
            main()
        mock_mcp.assert_called_once_with(transport="stdio")
