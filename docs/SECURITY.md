# Security model

## Threat model

**Adversary 1 — Prompt injection in the agent.** A malicious document, web
page, or tool response tricks the LLM into requesting a destructive command
(e.g. `rm -rf /`, `uci set ...`, `reboot`). **Defence:** the command
allowlist (read + write) blocks anything not explicitly whitelisted. Even a
fully compromised agent can only request commands in the allowlist.

**Adversary 2 — Network MITM.** An attacker on the LAN intercepts SSH to the
router (ARP spoofing, evil twin). **Defence:** strict SSH host-key
verification, trust-on-first-use by default, with a clear refusal on key
change (see [Host-key verification](#host-key-verification)).

**Adversary 3 — Compromised process.** An attacker reads or tampers with
the MCP server's logs, audit log, or response payloads to exfiltrate WiFi
PSKs, passwords, or tokens. **Defence:** secret redaction at the response
boundary and in log lines; audit log is append-only with size rotation.

**Adversary 4 — Local privilege escalation on the host running the server.**
The MCP server has the SSH private key for the router and can read
unredacted logs before sanitisation. **Defence:** keep the host secure
(standard SSH hardening, encrypted filesystem, file permissions on
`~/.ssh/openwrt_mcp_ed25519` and `~/.config/openwrt-mcp/known_hosts` set to
`0600`). The TOFU pin path is chmod'd `0600` automatically on first write.

## Host-key verification

Configured by `OPENWRT_HOST_KEY_POLICY` and `OPENWRT_KNOWN_HOSTS`:

| `OPENWRT_HOST_KEY_POLICY` | `OPENWRT_KNOWN_HOSTS` | TOFU store exists? | Behaviour |
|---|---|---|---|
| `none` | * | * | Accept any host key (legacy — discouraged) |
| `tofu` (default) | set | — | Strict verification against the given file |
| `tofu` (default) | unset | yes | Strict verification against the TOFU store |
| `tofu` (default) | unset | no  | Trust-on-first-use: connect, pin, warn |

Default store path: `~/.config/openwrt-mcp/known_hosts` (created with mode
`0600` on first connect).

**On key change:** the server logs

```
HOST KEY VERIFICATION FAILED for <host>:<port>. If this key change is
intentional, update the known-hosts store at <path> (or set
OPENWRT_HOST_KEY_POLICY=none to opt out). Refusing to connect.
```

and refuses to connect. To accept a new key (e.g. router reinstalled), edit
the store or set the policy to `none` temporarily.

## Command allowlists

Two allowlists, both anchored with `re.fullmatch`:

- **Read** (`SecurityValidator.ALLOWED_PATTERNS`) — 30+ patterns covering
  ubus, uci (read), iptables / nft, logread, /proc reads, opkg list/info,
  ping/traceroute/nslookup, WiFi scan.
- **Write** (`SecurityValidator.ALLOWED_WRITE_PATTERNS`) — 7 patterns:
  `ifdown <iface>`, `ifup <iface>`, `/etc/init.d/network {reload,restart}`,
  `uci set <k>=<v>`, `uci commit <k>`, `ubus call system reboot`. The
  interface name is validated separately (lowercase, max 15 chars, `lo`
  blocked).

Metacharacters rejected before both allowlists: `;`, `&&`, `||`, `|`, `$(`,
backticks, `$`, `{`, `}`, `\n`, `\r`. `uci set` values are further limited
to `[A-Za-z0-9_.,:/@-]+` so they are not interpolated raw.

## Audit log

Set `AUDIT_LOG_FILE` to `~/.local/state/openwrt-mcp/audit.log` (outside
the git tree). The file is appended with one line per executed command:

```
2026-09-01T17:15:42 | <request-uuid> | root@<router> | <command>
```

- Rotates at 5 MB (`.log` → `.log.1`).
- Writes log a warning rather than silently dropping on failure.
- Redacted by `sanitize_log_line()` before reaching the application logger.

## Response sanitisation

`sanitize_response_data()` recursively redacts values keyed
`password|passwd|psk|secret|token|key|api_key|pre_shared` from every
tool payload before it leaves the server. IPs and MACs are *intentionally*
preserved — reporting DHCP leases and connectivity tests is the server's
job. WiFi pre-shared keys (`key='...'`) are the secret and are redacted.

## Known limitations

- **WiFi PSKs as a structural pattern, not as content.** If a UCI value is
  named in a way not covered by the redaction pattern, it can leak. The pattern
  set is wide enough to cover all upstream UCI sections but is not a parser.
- **v4.0.0 removed the HTTP surface.** SSE, Health, and REST sidecars are
  gone, so the former unauthenticated-local-HTTP and
  `MCP_UNSAFE_PUBLIC_ACCESS_CONFIRMED` limitations no longer apply. The only
  process boundary is stdio owned by the MCP client.
- **Single-router assumption.** Host-key pinning is per host:port, not per
  fingerprint — you can have one entry per router.
- **`OPENWRT_HOST_KEY_POLICY=none`** explicitly disables all host-key checks.
  Useful only for ephemeral CI or air-gapped labs.