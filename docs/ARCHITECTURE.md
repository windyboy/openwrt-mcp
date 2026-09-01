# Architecture

## Components

```
┌──────────────────┐
│  MCP client      │   Claude / opencode / LibreChat / VS Code
└────────┬─────────┘
         │  stdio  (NEW)
         │  OR  SSE / streamable-http
         ▼
┌──────────────────┐
│  openwrt-mcp     │   Python — FastMCP v3
│  ┌────────────┐  │
│  │ server.py  │──┼─► health :9094 (SSE mode only)
│  │            │  │   REST   :9096 (SSE mode only)
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

## Module map

| Module | Role |
|---|---|
| `openwrt_mcp.server` | FastMCP server, transport selection, health/REST threads (SSE mode only) |
| `openwrt_mcp.tools.registration` | Tool catalog, write-tool gating |
| `openwrt_mcp.tools.explorer` | Read-only tool implementations (24) |
| `openwrt_mcp.tools.writer` | Write tool implementations (5) — gated by `ENABLE_WRITE_OPERATIONS=1` |
| `openwrt_mcp.tools.ssh_client` | Connection management, command execution, audit log |
| `openwrt_mcp.validators` | Default-deny command whitelist (read + write allowlists) |
| `openwrt_mcp.sanitizer` | Secret/credential redaction in logs and responses |
| `openwrt_mcp.observability` | Per-request IDs, structured logging |

## Transports

Two transports are supported via `--transport`:

- **`stdio`** (NEW in 3.5.0) — MCP over stdin/stdout. The client (opencode,
  Claude Desktop, …) owns the process lifecycle. Health/REST servers are not
  started — they would just bind ports nothing uses. This is the recommended
  transport for single-user setups.
- **`sse`** — MCP over Server-Sent Events on `MCP_SSE_PORT` (default 9095).
  Useful when multiple clients share one server, or when the client only
  supports HTTP-based transports (LibreChat). Also starts a health endpoint
  on 9094 and a REST API on 9096.

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