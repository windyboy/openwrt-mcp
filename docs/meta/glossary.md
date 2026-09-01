---
description: Central glossary of domain terms used across project documentation
doc_id: ref.glossary
type: ref
status: active
rigor_tier: L0
ttl_days: 180
stability: stable
ai_scope: editable
source_of_truth: true
upstream: []
last_verified: 2026-09-01
owners: ["backend-team"]
---

# Glossary

- `MCP`: Model Context Protocol — protocol for communication between
  AI agents and tools/servers
- `stdio`: The only transport this server speaks (stdin/stdout JSON-RPC).
  The MCP client owns the process lifecycle.
- `SSE`: Server-Sent Events — HTTP MCP transport used in 3.x; **removed
  in 4.0.0**. Not a current operator path.
- `XDG env`: Operator config at `~/.config/openwrt-mcp/env`; audit at
  `~/.local/state/openwrt-mcp/audit.log`; TOFU pins at
  `~/.config/openwrt-mcp/known_hosts`
- `OpenWRT`: Linux distribution for routers based on Buildroot
- `UCI`: Unified Configuration Interface — configuration framework
  on OpenWRT
- `ubus`: OpenWRT micro bus IPC for communicating with system
  services
- `DHCP`: Dynamic Host Configuration Protocol — automatic IP
  address assignment
- `SSH`: Secure Shell — encrypted remote access protocol
- `FastMCP`: Python framework for building MCP servers
- `asyncssh`: Asynchronous SSH library for Python
- `TOFU`: Trust-on-first-use SSH host-key pinning (default policy)
- `SecurityValidator`: Allowlist + metacharacter filter for SSH commands
  (read and write paths)
- `UCI value allowlist`: `[A-Za-z0-9_.,:/@-]+` charset for `uci set` values
- `ValidationError`: Exception class for input validation failures
- `ruff`: Python linter and formatter used in CI
- `mypy`: Static type checker used in CI
- `bandit`: Security linter used in CI
