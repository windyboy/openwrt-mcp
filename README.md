# openwrt-mcp

A read-only-by-default [Model Context Protocol](https://modelcontextprotocol.io/)
server for OpenWRT routers. Speaks to the router over SSH (key auth) with a
default-deny command allowlist, so even a prompt-injected agent can only
request operations that have been explicitly whitelisted.

```text
MCP client ──► openwrt-mcp ──► SSH ──► OpenWRT router
                (whitelist + audit + host-key pin)
```

## Features

- **Default-deny command allowlist** — every SSH command is matched against
  a strict, anchored regex allowlist before it leaves the box.
- **24 tools** — system info, WiFi status, DHCP leases, firewall rules,
  OpenThread (when present), UCI read, log search, package list, ping /
  traceroute / nslookup, WiFi scan.
- **Write tools gated by `ENABLE_WRITE_OPERATIONS=1`** — `uci set`, `uci
  commit`, `ifdown`/`ifup`, `/etc/init.d/network reload|restart`,
  `ubus call system reboot`. Read-only by default.
- **SSH host-key verification** with trust-on-first-use by default and a
  clear refusal on key change.
- **Audit log** with 5 MB rotation and timestamped request IDs.
- **Two transports** — local **stdio** (preferred for single-user setups)
  or SSE on `127.0.0.1:9095` for HTTP-based clients.
- **Secret redaction** at the response boundary: WiFi PSKs, passwords, and
  tokens cannot leak even if a tool forgets to sanitise.

## Install (uv)

```bash
git clone <repo-url> openwrt-mcp
cd openwrt-mcp
uv sync --extra dev
```

## Configure

All configuration is via environment variables. Create a `.env` or export
them in your shell:

```bash
export OPENWRT_HOST=192.168.1.1
export OPENWRT_SSH_KEY=$HOME/.ssh/openwrt_mcp_ed25519
export ENABLE_WRITE_OPERATIONS=false     # true to enable write tools
export ENABLE_AUDIT_LOGGING=true
export AUDIT_LOG_FILE=$PWD/audit/openwrt_mcp.log
export LOG_LEVEL=INFO
```

The SSH key must already be authorised on the router
(`ssh-copy-id -i ~/.ssh/openwrt_mcp_ed25519.pub root@<host>`).

## Run

**stdio** — preferred for local MCP clients:

```bash
uv run openwrt-mcp --transport stdio
```

**SSE** — for HTTP-based MCP clients (LibreChat, …). Also starts a health
endpoint on `:9094` and a REST API on `:9096`:

```bash
uv run openwrt-mcp --transport sse
```

Wire it into opencode's `mcp` config:

```jsonc
{
  "mcp": {
    "openwrt": {
      "type": "local",
      "command": ["uv", "run", "--directory", "/path/to/openwrt-mcp",
                  "openwrt-mcp", "--transport", "stdio"],
      "environment": {
        "OPENWRT_HOST": "192.168.1.1",
        "OPENWRT_SSH_KEY": "/home/you/.ssh/openwrt_mcp_ed25519",
        "ENABLE_WRITE_OPERATIONS": "false"
      },
      "enabled": true
    }
  }
}
```

## Configuration reference

| Variable | Default | Description |
|---|---|---|
| `OPENWRT_HOST` | — | Router IP or hostname |
| `OPENWRT_PORT` | `22` | SSH port |
| `OPENWRT_USER` | `root` | SSH username |
| `OPENWRT_SSH_KEY` | — | Path to SSH private key |
| `OPENWRT_PASSWORD` | — | SSH password (discouraged — use keys) |
| `OPENWRT_KNOWN_HOSTS` | — | Path to an OpenSSH known_hosts file (strict mode) |
| `OPENWRT_HOST_KEY_POLICY` | `tofu` | `tofu` (default) or `none` |
| `ENABLE_WRITE_OPERATIONS` | `false` | Set to `true` to register write tools |
| `ENABLE_AUDIT_LOGGING` | `true` | Log every executed command |
| `AUDIT_LOG_FILE` | `/app/log/openwrt_mcp.log` | Audit log path |
| `MCP_TRANSPORT` | `sse` | `sse` or `stdio` (also `--transport` flag) |
| `MCP_SSE_PORT` | `9095` | SSE port (sse transport only) |
| `HEALTH_PORT` | `9094` | Health port (sse transport only) |
| `REST_API_PORT` | `9096` | REST port (sse transport only) |
| `LOG_LEVEL` | `INFO` | Standard logging level |

## Security model

See [`docs/SECURITY.md`](docs/SECURITY.md) for the threat model and the
command allowlist in detail. The short version: **the router is root**, so
the server is built to refuse anything not explicitly whitelisted, verify
the router's identity, and leave an audit trail of every command.

## Architecture

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the module map,
transports, and the security layers in execution order.

## Development

```bash
uv sync --extra dev
uv run pytest tests/unit -q
uv run ruff check .
uv run ruff format --check .
uv run mypy src/openwrt_mcp --strict
```

See [`CONTRIBUTING.md`](CONTRIBUTING.md).

## Acknowledgements

Forked from [paulomac1000/openwrt-mcp](https://github.com/paulomac1000/openwrt-mcp),
which itself was forked from [jsebgiraldo/openwrt_ssh_mcp](https://github.com/jsebgiraldo/openwrt_ssh_mcp).
Both upstream projects are MIT-licensed.

## License

MIT — see [`LICENSE`](LICENSE).