"""Tests for security hardening: host-key TOFU, audit rotation, validator fixes."""

import logging

from openwrt_mcp.tools import ssh_client as ssh_client_mod
from openwrt_mcp.tools.ssh_client import (
    SSHConnection,
    _host_pattern,
    _key_fingerprint,
    _known_hosts_entry,
)
from openwrt_mcp.validators import SecurityValidator

# ---------------------------------------------------------------------------
# Validator hardening
# ---------------------------------------------------------------------------


class TestValidatorHardening:
    def test_embedded_newline_rejected(self):
        ok, msg = SecurityValidator.validate_command("ping -c 1 example\nreboot")
        assert not ok
        assert "Blocked dangerous character" in msg

    def test_carriage_return_rejected(self):
        ok, msg = SecurityValidator.validate_command("logread\rreboot")
        assert not ok

    def test_nft_stderr_redirect_still_allowed(self):
        ok, msg = SecurityValidator.validate_command("nft list ruleset 2>/dev/null")
        assert ok, msg

    def test_redirect_to_file_rejected(self):
        ok, _ = SecurityValidator.validate_command("nft list ruleset >/tmp/x")
        assert not ok

    def test_plain_allowlisted_command_still_passes(self):
        ok, msg = SecurityValidator.validate_command("ubus call system board")
        assert ok, msg

    def test_read_write_patterns_still_separate(self):
        ok, _ = SecurityValidator.validate_command("uci commit network")
        assert not ok
        ok, _ = SecurityValidator.validate_write_command("uci commit network")
        assert ok


class TestWritePathValidation:
    def test_happy_path_uci_set_still_allowed(self):
        ok, msg = SecurityValidator.validate_write_command("uci set network.wan.ipaddr=10.0.0.1")
        assert ok, msg

    def test_command_substitution_rejected(self):
        ok, msg = SecurityValidator.validate_write_command("uci set network.lan.ipaddr=$(reboot)")
        assert not ok
        assert "Blocked dangerous character" in msg

    def test_backticks_rejected(self):
        ok, msg = SecurityValidator.validate_write_command("uci set network.lan.ipaddr=`id`")
        assert not ok
        assert "Blocked dangerous character" in msg

    def test_semicolon_rejected(self):
        ok, msg = SecurityValidator.validate_write_command(
            "uci set network.lan.hostname=foo;reboot"
        )
        assert not ok
        assert "Blocked dangerous character" in msg

    def test_newline_rejected(self):
        ok, msg = SecurityValidator.validate_write_command(
            "uci set network.lan.hostname=foo\nreboot"
        )
        assert not ok
        assert "Blocked dangerous character" in msg

    def test_carriage_return_rejected(self):
        ok, _ = SecurityValidator.validate_write_command("uci set network.lan.hostname=foo\rreboot")
        assert not ok

    def test_uci_value_allowlist_rejects_quotes_and_spaces(self):
        ok, _ = SecurityValidator.validate_uci_value("foo;reboot")
        assert not ok
        ok, _ = SecurityValidator.validate_uci_value("a b")
        assert not ok
        ok, _ = SecurityValidator.validate_uci_value("x'y")
        assert not ok
        ok, msg = SecurityValidator.validate_uci_value("10.0.0.1")
        assert ok, msg
        ok, msg = SecurityValidator.validate_uci_value("/etc/config/network")
        assert ok, msg


# ---------------------------------------------------------------------------
# known_hosts helpers
# ---------------------------------------------------------------------------

_PUBKEY = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIExampleKeyData00000000000000000000="


class TestKnownHostsHelpers:
    def test_host_pattern_default_port(self):
        assert _host_pattern("10.0.0.2", 22) == "10.0.0.2"

    def test_host_pattern_custom_port(self):
        assert _host_pattern("10.0.0.2", 2222) == "[10.0.0.2]:2222"

    def test_known_hosts_entry_format(self):
        entry = _known_hosts_entry("10.0.0.2", 22, _PUBKEY)
        assert entry == f"10.0.0.2 {_PUBKEY}"

    def test_fingerprint_format(self):
        fp = _key_fingerprint(_PUBKEY)
        assert fp.startswith("SHA256:")
        assert "=" not in fp


# ---------------------------------------------------------------------------
# Host-key policy resolution
# ---------------------------------------------------------------------------


class TestHostKeyPolicy:
    def test_policy_none_accepts_any(self, monkeypatch):
        monkeypatch.setattr(ssh_client_mod, "HOST_KEY_POLICY", "none")
        monkeypatch.setattr(ssh_client_mod, "OPENWRT_KNOWN_HOSTS", "/tmp/strict")
        monkeypatch.setattr(ssh_client_mod, "TOFU_KNOWN_HOSTS_PATH", "/tmp/store")
        assert SSHConnection._resolve_host_key_policy() == (None, False)

    def test_explicit_known_hosts_is_strict(self, monkeypatch):
        monkeypatch.setattr(ssh_client_mod, "HOST_KEY_POLICY", "tofu")
        monkeypatch.setattr(ssh_client_mod, "OPENWRT_KNOWN_HOSTS", "/tmp/strict")
        assert SSHConnection._resolve_host_key_policy() == ("/tmp/strict", False)

    def test_existing_tofu_store_is_strict(self, monkeypatch, tmp_path):
        store = tmp_path / "known_hosts"
        store.write_text("")
        monkeypatch.setattr(ssh_client_mod, "HOST_KEY_POLICY", "tofu")
        monkeypatch.setattr(ssh_client_mod, "OPENWRT_KNOWN_HOSTS", None)
        monkeypatch.setattr(ssh_client_mod, "TOFU_KNOWN_HOSTS_PATH", str(store))
        assert SSHConnection._resolve_host_key_policy() == (str(store), False)

    def test_missing_store_triggers_tofu(self, monkeypatch, tmp_path):
        store = tmp_path / "missing" / "known_hosts"
        monkeypatch.setattr(ssh_client_mod, "HOST_KEY_POLICY", "tofu")
        monkeypatch.setattr(ssh_client_mod, "OPENWRT_KNOWN_HOSTS", None)
        monkeypatch.setattr(ssh_client_mod, "TOFU_KNOWN_HOSTS_PATH", str(store))
        assert SSHConnection._resolve_host_key_policy() == (None, True)


# ---------------------------------------------------------------------------
# Audit logging
# ---------------------------------------------------------------------------


class TestAuditLogging:
    def _conn(self) -> SSHConnection:
        return SSHConnection()

    def test_audit_entry_written(self, monkeypatch, tmp_path):
        audit = tmp_path / "audit" / "openwrt_mcp.log"
        monkeypatch.setattr(ssh_client_mod, "AUDIT_LOG_FILE", str(audit))
        self._conn()._log_audit("ubus call system board")
        content = audit.read_text(encoding="utf-8")
        assert "ubus call system board" in content
        assert len(content.splitlines()) == 1

    def test_audit_rotation(self, monkeypatch, tmp_path):
        audit = tmp_path / "audit" / "openwrt_mcp.log"
        audit.parent.mkdir(parents=True)
        audit.write_text("x" * 600)
        monkeypatch.setattr(ssh_client_mod, "AUDIT_LOG_FILE", str(audit))
        monkeypatch.setattr(ssh_client_mod, "_AUDIT_LOG_MAX_BYTES", 512)
        self._conn()._log_audit("free")
        assert audit.with_suffix(".log.1").exists()
        assert "free" in audit.read_text(encoding="utf-8")

    def test_audit_failure_not_silent(self, monkeypatch, tmp_path, caplog):
        blocker = tmp_path / "blocker"
        blocker.write_text("")
        monkeypatch.setattr(ssh_client_mod, "AUDIT_LOG_FILE", str(blocker / "child" / "audit.log"))
        with caplog.at_level(logging.WARNING, logger="root"):
            self._conn()._log_audit("free")
        assert any("Audit log write failed" in r.message for r in caplog.records)

    def test_rotation_cleans_up(self, monkeypatch, tmp_path):
        audit = tmp_path / "audit" / "openwrt_mcp.log"
        monkeypatch.setattr(ssh_client_mod, "AUDIT_LOG_FILE", str(audit))
        conn = self._conn()
        conn._log_audit("a")
        conn._log_audit("b")
        lines = audit.read_text(encoding="utf-8").splitlines()
        assert len(lines) == 2
