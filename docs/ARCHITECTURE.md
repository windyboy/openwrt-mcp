# Architecture

## Components

```
┌──────────────────┐
│  MCP client      │   Claude / opencode / VS Code
└────────┬─────────┘
         │  stdio (stdin/stdout)
         ▼
┌──────────────────┐
│  openwrt-mcp     │   Python — FastMCP v3, one process
│  ┌────────────┐  │
│  │ server.py  │  │   mcp.run(transport="stdio")
│  └─────┬──────┘  │
│        │         │
│  ┌─────▼──────┐  │
│  │ validators │  │   whitelist + metachar blocklist
│  └─────┬──────┘  │
│  ┌─────▼──────┐  │
│  │ ssh_client │──┼─► asyncssh (TOFU host-key pin)
│  └────────────┘  │
│  audit logger       append + 5 MB rotation
└────────┬───────────┘
         │  SSH (ed25519 key auth, host key verified)
         ▼
┌──────────────────┐
│  OpenWRT router  │   ubus / uci / fw4 / iwinfo / opkg
└──────────────────┘
```

One process, one transport, one boundary (stdout). There is no HTTP sidecar.

## Module map

| Module | Role |
|---|---|
| `openwrt_mcp.server` | FastMCP server, stdio transport, tool helpers |
| `openwrt_mcp.tools.registration` | Tool catalog, write-tool gating |
| `openwrt_mcp.tools.explorer` | Read-only tool implementations (24) |
| `openwrt_mcp.tools.writer` | Write tool implementations (5) — gated by `ENABLE_WRITE_OPERATIONS=1` |
| `openwrt_mcp.tools.ssh_client` | Connection management, command execution, audit log |
| `openwrt_mcp.validators` | Default-deny command whitelist (read + write allowlists) |
| `openwrt_mcp.sanitizer` | Secret/credential redaction in logs and responses |
| `openwrt_mcp.observability` | Per-request IDs, structured logging |

## Transport

**stdio only.** MCP over stdin/stdout. The client (opencode, Claude Desktop, …)
owns the process lifecycle. `uv run openwrt-mcp` binds no ports.

SSE / Health / REST sidecars were removed in 4.0.0. HTTP-based MCP clients
should sit behind a stdio→HTTP bridge rather than this process.

## Security layers (defence in depth)

1. **Tool gating** — write tools are registered as no-ops unless
   `ENABLE_WRITE_OPERATIONS=1`.
2. **Command allowlist** — every SSH command must `re.fullmatch` a strict
   read allowlist (`^ubus call system board$`, `^uci show ...`, ...).
3. **Metachar blocklist** — `;`, `&&`, `|`, `$(`, backticks, newlines are
   rejected before the allowlist is consulted.
4. **Blocklist** — additional dangerous patterns (`rm`, `uci set`, `reboot`,
   redirects to anywhere but `/dev/null`, …).
5. **SSH host-key verification** — trust-on-first-use by default, strict when a
   known-hosts file exists, opt-out via `OPENWRT_HOST_KEY_POLICY=none`.
6. **Audit logging** — every executed command is timestamped and written to
   `AUDIT_LOG_FILE` with 5 MB rotation.
7. **Response sanitisation** — secrets (WiFi PSKs, passwords, tokens) are
   redacted at the response boundary; a tool that forgets to redact cannot
   leak a secret.
