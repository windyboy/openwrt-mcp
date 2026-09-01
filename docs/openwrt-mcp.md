---
description: Complete reference for OpenWRT-MCP server covering architecture, configuration, MCP tools, security design, testing, and stdio transport
doc_id: ref.openwrt-mcp
type: ref
status: active
rigor_tier: L2
ttl_days: 180
stability: stable
ai_scope: editable
domain: mcp
tags: ["openwrt", "mcp", "router", "ssh", "read-only"]
upstream:
  - ref.documentation-standard
source_of_truth: true
last_verified: 2026-09-01
owners: ["backend-team"]
---

# OpenWRT-MCP Reference

## PURPOSE

Provide secure, read-only SSH access to an OpenWRT router through the
Model Context Protocol. Enables AI assistants to query router status,
network configuration, WiFi clients, firewall rules, and system logs
without any ability to modify the system by default.

Key design decisions:
- Read-only by default — all SSH commands are whitelisted; write operations
  require `ENABLE_WRITE_OPERATIONS=1`
- Command whitelist — only explicit read-only patterns allowed
- Python-side command validation before SSH execution
- Standalone single Python process, no external databases

## SCOPE

- INCLUDED: MCP server architecture, 24 MCP tool
  catalog, SSH security whitelist, configuration
  environment variables, test suite structure,
  build system, CI pipeline
- EXCLUDED: MCP protocol specification, client-side tool calling,
  CI infrastructure configuration, OpenWRT router firmware
  configuration, network topology outside the router

## DEFINITIONS

- `MCP Server`: A FastMCP-based process exposing OpenWRT tools over
  stdio MCP transport
- `OpenWRT Router`: Target device running OpenWRT with SSH enabled
- `SecurityValidator`: Whitelist-based command filter preventing
  command injection
- `SSH Connection`: asyncssh-based connection manager with
  auto-reconnect, timeout handling, and audit logging
- `UCI`: Unified Configuration Interface — system configuration
  framework on OpenWRT
- `ubus`: OpenWRT micro bus IPC for service communication
- `FastMCP`: Python framework for building MCP servers
- `stdio`: MCP transport over stdin/stdout; the client owns the process

## RULES

1. System MUST validate all SSH commands through
   `SecurityValidator.validate_command()` before execution
2. System MUST block shell metacharacters: ; | & $ ` ( ) { } < > \0
3. System MUST block destructive commands: rm, reboot, halt, poweroff,
   wget, curl, dd, mkfs, mv, chmod, chown
4. System MUST block UCI write operations: uci set, add, remove,
   delete, rename, revert, commit
5. System MUST block package modifications: opkg install, remove,
   upgrade, update, configure
6. System MUST block pipe-to-shell patterns: | sh, | bash, | ash
7. System MUST use try/except Exception in every tool wrapper
8. System MUST return structured JSON with `"success"` boolean from
   every tool
9. System MUST return `_meta` envelope with `request_id`, `duration_ms`,
   and `tool_version` for observed tools
10. System MUST log only to stderr — stdout corrupts MCP transport
11. System MUST speak MCP over stdio only (no HTTP sidecars)

## INTERFACES

### Transport

stdio only. The MCP client spawns `openwrt-mcp` and speaks JSON-RPC on
stdin/stdout. The process binds no TCP ports.

### Install (operator)

Install a frozen binary; do not bind the MCP client to `uv run` in a
git working tree. See `README.md`.

```bash
uv tool install git+https://github.com/windyboy/openwrt-mcp.git
# or from a clone: uv tool install .
```

Router env: `~/.config/openwrt-mcp/env` (mode `600`). Audit:
`~/.local/state/openwrt-mcp/audit.log`. Optional wrapper
`~/.config/openwrt-mcp/run` sources the env file and execs
`~/.local/bin/openwrt-mcp`. Reinstall after source changes:
`uv tool install --force .`

### MCP Tools

All 24 tools are exposed as MCP-tool functions via stdio transport.
Each tool is registered with FastMCP and wrapped in try/except.
Most I/O tools accept an optional `timeout_seconds` parameter (default: SSH_TIMEOUT).

| Tool | Risk | Description | Parameters | Since |
|------|------|-------------|------------|-------|
| `test_router_connection` | READ | Verify SSH connectivity to router | `timeout_seconds` | v1.0.0 |
| `get_router_info` | READ | System board, memory, uptime, release | `timeout_seconds` | v1.0.0 |
| `get_router_wifi_status` | READ | WiFi radios, SSIDs, connected clients | `timeout_seconds` | v1.0.0 |
| `get_router_dhcp_leases` | READ | Active DHCP leases with hostnames, MACs | `timeout_seconds` | v1.0.0 |
| `get_router_firewall_rules` | READ | iptables/nftables/fw4 firewall rules | `timeout_seconds` | v1.0.0 |
| `read_router_uci_config` | READ | UCI configuration sections | `config_name`, `timeout_seconds` | v1.0.0 |
| `list_router_packages` | READ | Installed OPKG packages | `timeout_seconds` | v1.0.0 |
| `get_router_logs` | READ | Recent system logs from logread | `lines`, `filter_level`, `timeout_seconds` | v1.0.0 |
| `search_router_logs` | READ | Filtered log search by pattern | `search_term`, `max_results`, `timeout_seconds` | v1.0.0 |
| `diagnose_router_connectivity` | READ | Ping and DNS resolution tests | `timeout_seconds` | v1.0.0 |
| `get_dhcp_static_leases` | READ | Static DHCP reservations from UCI | `timeout_seconds` | v1.0.0 |
| `search_dhcp_logs` | READ | Search DHCP events in logs | `search_term`, `timeout_seconds` | v1.0.0 |
| `get_device_dhcp_details` | READ | Full device info: lease, reservation, logs | `mac_address`, `ip_address`, `timeout_seconds` | v1.0.0 |
| `get_router_context` | READ | Unified router context snapshot | `timeout_seconds` | v1.2.0 |
| `describe_router_capabilities` | READ | Server capability introspection | None | v1.2.0 |
| `ping_host` | READ | Ping a host from the router | `host`, `count`, `timeout_seconds` | v1.2.0 |
| `traceroute_host` | READ | Traceroute to a host | `host`, `timeout_seconds` | v1.2.0 |
| `nslookup_host` | READ | DNS lookup from the router | `host`, `dns_server`, `timeout_seconds` | v1.2.0 |
| `wifi_scan` | READ | Scan neighboring WiFi networks | `radio`, `timeout_seconds` | v1.2.0 |
| `uci_set` | WRITE | Set UCI configuration value | `config`, `section`, `option`, `value`, `timeout_seconds` | v1.2.0 |
| `uci_commit` | WRITE | Commit UCI changes | `config`, `timeout_seconds` | v1.2.0 |
| `restart_interface` | WRITE | Restart a network interface | `interface_name`, `timeout_seconds` | v1.2.0 |
| `reload_network` | WRITE | Reload network services | `timeout_seconds` | v1.2.0 |
| `reboot_device` | WRITE | Reboot the router | `timeout_seconds` | v1.2.0 |

> WRITE tools require `ENABLE_WRITE_OPERATIONS=1` environment variable.

### Tool Response Format

Success:
```json
{"success": true, "data": <any>, "_meta": {"request_id": "...", "duration_ms": 42, "tool_version": "1.2.0", "cached": false, "retry_safe": true}}
```

Error:
```json
{"success": false, "error": "message"}
```

Extended error (L2+):
```json
{"success": false, "error": {"code": "INVALID_PARAM", "message": "...", "retryable": false, "suggestion": "..."}}
```

## STATE

### FastMCP Version Compatibility Layer

The project probes **four** tool storage locations in priority order
to remain compatible across FastMCP major versions (2.x and 3.x):

1. `_tool_manager._tools` dict — FastMCP 2.x primary
2. `_tools` dict — FastMCP 2.x alternate
3. `.tools` dict — FastMCP 2.x legacy
4. `list_tools()` async method — FastMCP 3.x

**Rule:** Every component that introspects FastMCP internals MUST
probe all four locations. This includes:

| Component | File | Status |
|-----------|------|--------|
| `get_all_tools()` | `server.py:121-134` | compliant |
| Manifest attachment | `registration.py:893-907` | compliant |
| `MCPWrapper._discover_tools()` | `tests/integration/mcp_wrapper.py` | compliant |
| `mock_mcp` fixture | `tests/unit/test_mcp_tools.py` | N/A (bypasses FastMCP) |

When calling `list_tools()` (async), use `getattr(mcp, "list_tools", None)` +
`asyncio.new_event_loop()` + `run_until_complete()` —
never `asyncio.run()` inside an existing event loop context.

### Project Structure

```
src/openwrt_mcp/
  server.py               # Entry point, stdio MCP transport
  validators.py           # SecurityValidator, ValidationError
  observability.py        # request_id, _meta envelope, per-tool counters
  tools/
    constants.py          # SSOT for all environment variable defaults
    ssh_client.py         # SSH connection manager, async
    explorer.py           # OpenWRTExplorer — all internal functions
    writer.py             # OpenWRTWriter — write operations (ifdown/ifup, network reload)
    ubus_client.py        # UbusClient — ubus JSON-RPC transport module
    response_helpers.py   # _success_response, _error_response helpers
    registration.py       # register_openwrt_tools — 24 MCP tool wrappers
  __main__.py              # python -m entry point
tests/
  unit/                   # 200 unit tests (all mocked, no I/O)
  integration/            # 53 integration tests (in-process MCP + real router)
  smoke/                  # response-contract smoke tests
  e2e/                    # end-to-end tests (in-process MCP)
```

### Environment Variables

Required:
| Variable | Default | Description |
|----------|---------|-------------|
| OPENWRT_HOST | — (required) | Router IP address |
| OPENWRT_SSH_KEY | ~/.ssh/openwrt_mcp_ed25519 | Path to SSH private key |

Optional:
| Variable | Default | Description |
|----------|---------|-------------|
| OPENWRT_PORT | 22 | SSH port |
| OPENWRT_USER | root | SSH username |
| OPENWRT_PASSWORD | None | Password (not recommended) |
| SSH_TIMEOUT | 30 | SSH connection timeout (seconds) |
| LOG_LEVEL | INFO | Logging level |
| ENABLE_AUDIT_LOGGING | true | Log all executed commands |
| AUDIT_LOG_FILE | ~/.local/state/openwrt-mcp/audit.log | Audit log file path |
| ENABLE_WRITE_OPERATIONS | false | Set to `1` or `true` to enable write tools (uci_set, uci_commit, restart_interface, reload_network, reboot_device) |

### Assumptions

- Target router runs OpenWRT with Dropbear or OpenSSH enabled
- SSH key-based authentication is configured on the router
- Server runs as a single Python process over stdio
- Python 3.14 or newer is available

### Constraints

- Maximum 24 registered MCP tools (19 read-only + 5 write when enabled)
- Single-router connection only (no multi-router support)
- Write operations require `ENABLE_WRITE_OPERATIONS=1` — disabled by default
- SSH timeout is configurable but bounded (default 30s)

### Known Limitations

- No multi-router support — one server instance serves one router
- Write operations disabled by default; require `ENABLE_WRITE_OPERATIONS=1`
- No configuration changes, package installations, or upgrades
- DHCP logs require `log_dhcp` option enabled in dnsmasq config
- Audit log file grows unbounded — rotation is operator responsibility

### Risks and Caveats

#### Write Tool Execution Risks

Write tools (`restart_interface`, `reload_network`, `reboot_device`,
`uci_set`, `uci_commit`) are guarded by
`ENABLE_WRITE_OPERATIONS=1` (default: false). When enabled, they can
cause irreversible side effects:

- **interface restart (ifdown/ifup):** Disabling a critical interface
  (LAN/WAN) can cause permanent connectivity loss requiring physical
  router reset. The `ifdown` command does not guarantee `ifup` will
  succeed on all router models.
- **network reload:** Temporarily disrupts all network services on the
  device.
- **device reboot:** Takes the router offline for 60+ seconds.
- **uci changes:** Incorrect or malformed UCI values can misconfigure
  firewall rules, network interfaces, DHCP settings, or wireless
  parameters — potentially locking out all access.

#### Write Command Validation Boundary

Write commands use a **separate validation path** (`execute_write()`
in `SSHConnection`) that checks `ALLOWED_WRITE_PATTERNS`. The standard
`execute()` path checks only `ALLOWED_PATTERNS` and **will reject**
any write command (ifdown, uci set/commit, ubus call system reboot,
init.d script reload). This boundary ensures read-only tools
can never accidentally execute write operations, even if the tool
code is modified.

Unit tests in `TestSecurityValidatorWriteCommands` enforce this
separation — every write command is verified to be rejected by
`validate_command()` and accepted only by `validate_write_command()`.

#### Mock Testing Strategy

Write tools are tested exclusively through mocks
(`tests/integration/test_write_tools_mocked.py`). Real router testing
is restricted to read-only operations. Response fixtures for
`uci_set` and `uci_commit` were collected once from a real device
using idempotent values (no actual configuration changes). Dangerous
tools (`restart_interface`, `reload_network`, `reboot_device`) have
response fixtures derived from code structure rather than real
execution, to avoid any risk of production router instability.

## EDGE_CASES

- CASE: Router SSH is unreachable
  EXPECTED: Tool returns `{"success": false, "error": "..."}` with
  status "disconnected". Server continues operating for retry.
- CASE: SSH key file not found at startup
  EXPECTED: Server logs warning, tools return connection errors on
  invocation. Server does not crash.
- CASE: Invalid config name passed to read_router_uci_config
  EXPECTED: Returns `INVALID_PARAM` error with list of valid config
  names and suggestion.
- CASE: Invalid MAC or IP format in get_device_dhcp_details
  EXPECTED: Returns `INVALID_PARAM` error with format suggestion.
- CASE: Client disconnects during long-running tool (diagnose)
  EXPECTED: stdio EOF ends the process. In-flight SSH work is abandoned.
- CASE: All backend connections fail at startup
  EXPECTED: Server starts, tools return connection errors.
- CASE: Banned search term passed to search_router_logs
  EXPECTED: Returns `INVALID_PARAM` error before any SSH call.
- CASE: MCP client closes stdin
  EXPECTED: Server exits; no leftover TCP listeners.

## EXAMPLES

### Run (stdio)

```bash
~/.config/openwrt-mcp/run
# development clone only: uv run openwrt-mcp
```

The MCP client owns the process and speaks JSON-RPC on stdin/stdout.
The process binds no TCP ports.

### Tool Manifest Shape

```json
{
  "name": "get_router_info",
  "version": "4.0.0",
  "risk": "READ",
  "side_effects": "read",
  "idempotent": true,
  "retryable": true,
  "concurrent_safe": false,
  "timeout_ms": 15000,
  "requires_confirmation": false,
  "determinism": "env-dependent",
  "latency": "moderate",
  "cost": "cheap"
}
```

### Run Unit Tests

```bash
pytest tests/unit/ -v --tb=short
```

### Run All Tests with Coverage

```bash
pytest tests/ --cov=openwrt_mcp --cov-fail-under=80 -v
```

## NON_GOALS

- Does not specify MCP wire protocol internals
- Does not define CI/CD pipeline configuration
- Does not cover OpenWRT router firmware configuration
- Does not provide multi-router or multi-device support
- Does not define client-side MCP tool calling patterns
- Does not replace OpenWRT vendor documentation
- Does not handle credential rotation or key management
- Does not define log retention or rotation policy

## CHANGELOG

### [1.2.0] — 2026-05-12
- Added get_router_context, describe_router_capabilities — unified context and introspection
- Added uci_set, uci_commit — UCI write operations (requires ENABLE_WRITE_OPERATIONS=1)
- Added reboot_device — router reboot (requires ENABLE_WRITE_OPERATIONS=1)
- Added ping_host, traceroute_host, nslookup_host — standalone network diagnostics
- Added wifi_scan — neighboring WiFi network survey
- Added JSON Schema documentation (schema/)
- Added execute_write() — separate write command validation path
- Added dynamic risk prefix injection (_inject_risk_prefixes)
- Added RISKS_AND_CAVEATS section
- Added ENABLE_WRITE_OPERATIONS environment variable
- Write command validation in SecurityValidator
- Update from 13 to 24 registered tools

### [1.1.0] — 2026-05-11
- Repository structure refactored: explorer.py split into 4 modules under tools/
- Python base image: 3.11-slim → 3.13-slim
- Added timeout_seconds param to all I/O tools
- Added MCPWrapper for integration tests
- Added _meta envelope (request_id, duration_ms, tool_version) on all tools
- Added SSHConnection cancellation support
- Fixed 8 bugs: timeout reset, concurrent_safe, gateway fallback, and similar
- 13 tools, 137 tests

### [1.0.0] — 2026-05-11
- Initial release with 13 read-only MCP tools
- Extended error responses with structured codes
- Tool manifests with capability descriptors
- Per-tool observability (request_id, _meta, counters)
- CI pipeline with ruff, mypy, bandit, coverage (80%)
- Smoke and E2E test suites
