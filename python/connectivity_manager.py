from __future__ import annotations

import logging
import os
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional
from urllib.error import URLError
from urllib.request import Request, urlopen


@dataclass
class ConnectivityStatus:
    interface_name: str
    interface_exists: bool
    lower_up: bool
    has_ipv4: bool
    internet_ok: bool
    health_url: str
    reason: str
    checked_time_s: float

    def to_dict(self) -> dict:
        return {
            "interface_name": self.interface_name,
            "interface_exists": self.interface_exists,
            "lower_up": self.lower_up,
            "has_ipv4": self.has_ipv4,
            "internet_ok": self.internet_ok,
            "health_url": self.health_url,
            "reason": self.reason,
            "checked_time_s": self.checked_time_s,
        }


class ConnectivityManager:
    """
    Lightweight network health checker for deployment runtime.

    Design goals:
        - Never block sensor processing indefinitely.
        - Use bounded command/network timeouts.
        - Avoid modem resets when link is already healthy.
    """

    def __init__(
        self,
        interface_name: str,
        health_url: str = "https://api.ipify.org",
        check_timeout_s: int = 5,
        at_port: str = "/dev/ttyUSB6",
        at_baud: int = 115200,
        apn: str = "www",
        recovery_enabled: bool = True,
        recovery_min_interval_s: int = 20,
        recovery_max_interval_s: int = 300,
        dhcp_timeout_s: int = 25,
        lower_up_wait_timeout_s: int = 10,
        usb_discovery_timeout_s: int = 6,
        serial_probe_timeout_s: float = 0.8,
    ) -> None:
        self.interface_name = interface_name
        self.health_url = health_url
        self.check_timeout_s = max(1, int(check_timeout_s))
        self.at_port = at_port
        self.at_baud = int(at_baud)
        self.apn = apn
        self.recovery_enabled = recovery_enabled
        self.recovery_min_interval_s = max(5, int(recovery_min_interval_s))
        self.recovery_max_interval_s = max(
            self.recovery_min_interval_s,
            int(recovery_max_interval_s),
        )
        self.dhcp_timeout_s = max(5, int(dhcp_timeout_s))
        self.lower_up_wait_timeout_s = max(2, int(lower_up_wait_timeout_s))
        self.usb_discovery_timeout_s = max(1, int(usb_discovery_timeout_s))
        self.serial_probe_timeout_s = max(0.2, float(serial_probe_timeout_s))

        self._last_recovery_attempt_s = 0.0
        self._recovery_fail_count = 0

    def check(self) -> ConnectivityStatus:
        status = self._evaluate_connectivity_status()

        if status.internet_ok:
            self._recovery_fail_count = 0
            return status

        if not self.recovery_enabled:
            return status

        now_s = time.time()
        if not self._recovery_backoff_elapsed(now_s):
            return status

        recovery_note = self._attempt_recovery(status)
        self._last_recovery_attempt_s = now_s

        post_status = self._evaluate_connectivity_status()
        if post_status.internet_ok:
            self._recovery_fail_count = 0
            post_status.reason = (
                f"Recovery succeeded. Prior state: {status.reason}. "
                f"Actions: {recovery_note}"
            )
            return post_status

        self._recovery_fail_count += 1
        post_status.reason = (
            f"{post_status.reason} | Recovery attempt failed. Actions: {recovery_note}"
        )
        return post_status

    def _evaluate_connectivity_status(self) -> ConnectivityStatus:
        now_s = time.time()

        if not self.interface_name:
            return ConnectivityStatus(
                interface_name="",
                interface_exists=False,
                lower_up=False,
                has_ipv4=False,
                internet_ok=False,
                health_url=self.health_url,
                reason="MODEM_INTERFACE is not configured.",
                checked_time_s=now_s,
            )

        interface_exists = self._interface_exists(self.interface_name)
        if not interface_exists:
            return ConnectivityStatus(
                interface_name=self.interface_name,
                interface_exists=False,
                lower_up=False,
                has_ipv4=False,
                internet_ok=False,
                health_url=self.health_url,
                reason="Interface not found.",
                checked_time_s=now_s,
            )

        lower_up = self._lower_up(self.interface_name)
        has_ipv4 = self._has_ipv4(self.interface_name)

        if not lower_up:
            return ConnectivityStatus(
                interface_name=self.interface_name,
                interface_exists=True,
                lower_up=False,
                has_ipv4=has_ipv4,
                internet_ok=False,
                health_url=self.health_url,
                reason="Interface exists but is not LOWER_UP.",
                checked_time_s=now_s,
            )

        if not has_ipv4:
            return ConnectivityStatus(
                interface_name=self.interface_name,
                interface_exists=True,
                lower_up=True,
                has_ipv4=False,
                internet_ok=False,
                health_url=self.health_url,
                reason="Interface is up but has no IPv4 address.",
                checked_time_s=now_s,
            )

        internet_ok, reason = self._internet_ok(self.health_url, self.check_timeout_s)

        return ConnectivityStatus(
            interface_name=self.interface_name,
            interface_exists=True,
            lower_up=True,
            has_ipv4=True,
            internet_ok=internet_ok,
            health_url=self.health_url,
            reason=reason,
            checked_time_s=now_s,
        )

    def _recovery_backoff_elapsed(self, now_s: float) -> bool:
        retry_window_s = min(
            self.recovery_max_interval_s,
            self.recovery_min_interval_s * (2 ** self._recovery_fail_count),
        )
        return (now_s - self._last_recovery_attempt_s) >= retry_window_s

    def _attempt_recovery(self, status: ConnectivityStatus) -> str:
        actions: list[str] = []
        logging.info(
            "Connectivity stage=recovery_start iface=%s exists=%s lower_up=%s ipv4=%s reason=%s",
            status.interface_name,
            status.interface_exists,
            status.lower_up,
            status.has_ipv4,
            status.reason,
        )

        modem_info = self._query_modem_state()
        if modem_info is not None:
            at_ok = bool(modem_info.get("at_ok", False))
            sim_ready = bool(modem_info.get("sim_ready", False))
            registered = modem_info.get("registered", False)
            attached = modem_info.get("attached", False)
            resolved_port = str(modem_info.get("at_port", self.at_port))

            # Trigger data session only when modem is ready and interface is NO-CARRIER.
            if not status.lower_up and at_ok and sim_ready and registered and attached:
                ok = self._send_at_command("AT+QNETDEVCTL=1,1,1", at_port=resolved_port)
                actions.append(f"QNETDEVCTL={'OK' if ok else 'FAIL'}")
                logging.info(
                    "Connectivity stage=qnetdevctl invoked=%s at_port=%s",
                    ok,
                    resolved_port,
                )
                if ok and status.interface_exists:
                    lower_up_ok = self._wait_for_lower_up(self.lower_up_wait_timeout_s)
                    actions.append(f"WAIT_LOWER_UP={'OK' if lower_up_ok else 'TIMEOUT'}")
            elif status.lower_up:
                actions.append("QNETDEVCTL=SKIP_LOWER_UP")
                logging.info(
                    "Connectivity stage=qnetdevctl invoked=false reason=already_lower_up"
                )
            else:
                actions.append("QNETDEVCTL=SKIP_MODEM_NOT_READY")
                logging.warning(
                    "Connectivity stage=qnetdevctl invoked=false at_ok=%s sim_ready=%s registered=%s attached=%s",
                    at_ok,
                    sim_ready,
                    registered,
                    attached,
                )

            # Keep APN sanity check lightweight and non-destructive.
            if self.apn:
                actions.append(f"APN={self.apn}")
        else:
            actions.append("MODEM_PROBE=FAIL")

        lower_up_now = status.lower_up
        has_ipv4_now = status.has_ipv4
        if status.interface_exists:
            lower_up_now = self._lower_up(self.interface_name)
            has_ipv4_now = self._has_ipv4(self.interface_name)

        if status.interface_exists and lower_up_now and not has_ipv4_now:
            dhcp_ok = self._run_dhcp_renew()
            actions.append(f"DHCP={'OK' if dhcp_ok else 'FAIL'}")
            logging.info("Connectivity stage=dhcp invoked=%s", dhcp_ok)
        elif status.interface_exists and not lower_up_now:
            actions.append("DHCP=SKIP_NO_LOWER_UP")
            logging.info("Connectivity stage=dhcp invoked=false reason=no_lower_up")
        else:
            actions.append("DHCP=SKIP_IPV4_PRESENT")
            logging.info("Connectivity stage=dhcp invoked=false reason=ipv4_present")

        if not actions:
            actions.append("NO_ACTION")

        return ", ".join(actions)

    def _query_modem_state(self) -> Optional[dict[str, Any]]:
        resolved_port = self._discover_responsive_at_port()
        if not resolved_port:
            logging.warning("Connectivity stage=modem_probe status=fail reason=no_at_responsive_ttyusb")
            return None

        try:
            import serial  # type: ignore
        except Exception:
            logging.warning("Connectivity stage=modem_probe status=fail reason=pyserial_unavailable")
            return None

        try:
            with serial.Serial(resolved_port, self.at_baud, timeout=2) as ser:
                at_lines = self._send_at_and_collect_lines(ser, "AT")
                cpin_lines = self._send_at_and_collect_lines(ser, "AT+CPIN?")
                reg_lines = self._send_at_and_collect_lines(ser, "AT+CEREG?")
                att_lines = self._send_at_and_collect_lines(ser, "AT+CGATT?")

            at_ok = any(line == "OK" for line in at_lines)
            sim_ready = any("+CPIN: READY" in line for line in cpin_lines)

            reg_ok = any(
                "+CEREG:" in line and (",1" in line or ",5" in line)
                for line in reg_lines
            )
            att_ok = any("+CGATT: 1" in line for line in att_lines)

            logging.info(
                "Connectivity stage=modem_probe status=ok at_port=%s at_ok=%s sim_ready=%s registered=%s attached=%s",
                resolved_port,
                at_ok,
                sim_ready,
                reg_ok,
                att_ok,
            )

            return {
                "at_port": resolved_port,
                "at_ok": at_ok,
                "sim_ready": sim_ready,
                "registered": reg_ok,
                "attached": att_ok,
            }
        except Exception as exc:
            logging.warning("Connectivity stage=modem_probe status=fail at_port=%s error=%s", resolved_port, exc)
            return None

    @staticmethod
    def _send_at_and_collect_lines(ser: object, command: str) -> list[str]:
        # pyserial.Serial supports these attributes/methods at runtime.
        serial_obj = ser  # type: ignore[assignment]
        serial_obj.reset_input_buffer()
        serial_obj.write((command + "\r").encode("utf-8"))
        time.sleep(0.35)

        lines: list[str] = []
        started = time.time()
        while time.time() - started < 2.0:
            raw = serial_obj.readline()
            if not raw:
                continue
            line = raw.decode("utf-8", errors="replace").strip()
            if not line:
                continue
            lines.append(line)
            if line in {"OK", "ERROR"}:
                break

        return lines

    def _send_at_command(self, command: str, at_port: Optional[str] = None) -> bool:
        port = at_port or self.at_port
        if not port or not os.path.exists(port):
            return False

        try:
            import serial  # type: ignore
        except Exception:
            return False

        try:
            with serial.Serial(port, self.at_baud, timeout=2) as ser:
                lines = self._send_at_and_collect_lines(ser, command)
            return any(line == "OK" for line in lines)
        except Exception as exc:
            logging.warning(
                "Connectivity stage=at_command status=fail command=%s at_port=%s error=%s",
                command,
                port,
                exc,
            )
            return False

    def _discover_responsive_at_port(self) -> Optional[str]:
        try:
            import serial  # type: ignore
        except Exception:
            logging.warning("Connectivity stage=at_port_discovery status=fail reason=pyserial_unavailable")
            return None

        deadline = time.time() + self.usb_discovery_timeout_s
        last_ports: list[str] = []

        while time.time() <= deadline:
            available_ports = sorted(str(path) for path in Path("/dev").glob("ttyUSB*"))
            last_ports = available_ports

            candidates: list[str] = []
            if self.at_port:
                candidates.append(self.at_port)
            candidates.extend(available_ports)

            seen: set[str] = set()
            for port in candidates:
                if port in seen:
                    continue
                seen.add(port)
                if not os.path.exists(port):
                    continue
                try:
                    with serial.Serial(port, self.at_baud, timeout=self.serial_probe_timeout_s) as ser:
                        lines = self._send_at_and_collect_lines(ser, "AT")
                    if any(line == "OK" for line in lines):
                        if port != self.at_port:
                            logging.info(
                                "Connectivity stage=at_port_discovery status=selected previous=%s selected=%s",
                                self.at_port,
                                port,
                            )
                        else:
                            logging.info(
                                "Connectivity stage=at_port_discovery status=confirmed selected=%s",
                                port,
                            )
                        self.at_port = port
                        return port
                except Exception:
                    continue

            time.sleep(0.3)

        logging.warning(
            "Connectivity stage=at_port_discovery status=fail configured=%s seen_ports=%s",
            self.at_port,
            ",".join(last_ports) if last_ports else "NONE",
        )
        return None

    def _wait_for_lower_up(self, timeout_s: int) -> bool:
        if not self.interface_name:
            return False

        deadline = time.time() + max(1, int(timeout_s))
        while time.time() <= deadline:
            if self._lower_up(self.interface_name):
                return True
            time.sleep(0.5)

        return False

    def _run_dhcp_renew(self) -> bool:
        dhclient_path = self._resolve_dhclient_path()
        if not dhclient_path:
            logging.warning(
                "Connectivity stage=dhcp status=fail reason=dhclient_not_found required_setup='Install dhclient and ensure command -v dhclient resolves a path.'"
            )
            return False

        try:
            result = subprocess.run(
                ["sudo", "-n", dhclient_path, "-v", self.interface_name],
                capture_output=True,
                text=True,
                timeout=self.dhcp_timeout_s,
                check=False,
            )
            if result.returncode != 0:
                logging.warning(
                    "Connectivity stage=dhcp status=fail command='sudo -n %s -v %s' rc=%s stderr=%s required_setup='Grant NOPASSWD for this command or a root-owned fixed-interface wrapper.'",
                    dhclient_path,
                    self.interface_name,
                    result.returncode,
                    (result.stderr or "").strip(),
                )
                return False
            logging.info(
                "Connectivity stage=dhcp status=ok command='sudo -n %s -v %s'",
                dhclient_path,
                self.interface_name,
            )
            return True
        except Exception as exc:
            logging.warning("Connectivity stage=dhcp status=fail reason=exception error=%s", exc)
            return False

    @staticmethod
    def _resolve_dhclient_path() -> Optional[str]:
        try:
            result = subprocess.run(
                ["/bin/sh", "-lc", "PATH=$PATH:/sbin:/usr/sbin; command -v dhclient"],
                capture_output=True,
                text=True,
                timeout=3,
                check=False,
            )
            path = (result.stdout or "").strip()
            if result.returncode == 0 and path and os.path.exists(path):
                return path
            return None
        except Exception:
            return None

    @staticmethod
    def _interface_exists(interface_name: str) -> bool:
        return Path(f"/sys/class/net/{interface_name}").exists()

    @staticmethod
    def _lower_up(interface_name: str) -> bool:
        carrier_path = Path(f"/sys/class/net/{interface_name}/carrier")
        operstate_path = Path(f"/sys/class/net/{interface_name}/operstate")

        carrier_up = False
        oper_up = False

        try:
            if carrier_path.exists():
                carrier_up = carrier_path.read_text(encoding="utf-8").strip() == "1"
        except Exception:
            carrier_up = False

        try:
            if operstate_path.exists():
                oper_up = operstate_path.read_text(encoding="utf-8").strip() == "up"
        except Exception:
            oper_up = False

        return carrier_up or oper_up

    @staticmethod
    def _has_ipv4(interface_name: str) -> bool:
        try:
            result = subprocess.run(
                ["ip", "-4", "-o", "addr", "show", "dev", interface_name, "scope", "global"],
                capture_output=True,
                text=True,
                timeout=3,
                check=False,
            )

            output = (result.stdout or "").strip()
            return " inet " in f" {output} "
        except Exception:
            return False

    @staticmethod
    def _internet_ok(health_url: str, timeout_s: int) -> tuple[bool, str]:
        req = Request(
            health_url,
            headers={"User-Agent": "riverguardian-runtime/1.0"},
            method="GET",
        )

        try:
            with urlopen(req, timeout=timeout_s) as resp:
                code = resp.getcode() or 0
                if 200 <= code < 400:
                    return True, "Internet health check succeeded."
                return False, f"Health check returned HTTP {code}."
        except URLError as exc:
            return False, f"Health check failed: {exc}"
        except Exception as exc:
            return False, f"Health check exception: {exc}"
