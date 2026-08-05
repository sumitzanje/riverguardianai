"""
RiverGuardian AI
Module 2: Bridge Interface

Purpose:
    Read structured JSON packets from the Arduino/STM32 sensor layer and
    provide validated data to the Python edge-AI pipeline.

Current mode:
    1. Serial mode for real Arduino/UNO Q hardware.
    2. Mock mode for local VS Code testing without hardware.

Expected Arduino packet:
{
    "node_id": "UB-01",
    "uptime_ms": 21272,
    "distance_cm": 189.3,
    "valid_samples": 3,
    "failed_samples": 0,
    "sensor_status": "OK"
}
"""

from __future__ import annotations

import json
import logging
import os
import socket
import time
from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class SensorPacket:
    """Validated sensor packet from the Arduino sensor node."""

    node_id: str
    uptime_ms: int
    distance_cm: Optional[float]
    raw_distance_cm: Optional[float]
    accepted_distance_cm: Optional[float]
    candidate_distance_cm: Optional[float]
    packet_sequence: Optional[int]
    fw_profile: Optional[str]
    fw_build: Optional[str]
    valid_samples: int
    failed_samples: int
    sensor_status: str
    measurement_state: str
    received_time_s: float
    error: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert packet to dictionary for downstream modules."""
        return {
            "node_id": self.node_id,
            "uptime_ms": self.uptime_ms,
            "distance_cm": self.distance_cm,
            "raw_distance_cm": self.raw_distance_cm,
            "accepted_distance_cm": self.accepted_distance_cm,
            "candidate_distance_cm": self.candidate_distance_cm,
            "packet_sequence": self.packet_sequence,
            "fw_profile": self.fw_profile,
            "fw_build": self.fw_build,
            "valid_samples": self.valid_samples,
            "failed_samples": self.failed_samples,
            "sensor_status": self.sensor_status,
            "measurement_state": self.measurement_state,
            "received_time_s": self.received_time_s,
            "error": self.error,
        }


class BridgeInterface:
    """
    Interface between Arduino sensor layer and Python AI layer.

    In real hardware mode, this reads JSON lines from serial.
    In mock mode, it generates realistic demo readings for development.
    """

    def __init__(
        self,
        serial_port: Optional[str] = None,
        baud_rate: int = 115200,
        monitor_endpoint: Optional[str] = None,
        mock_mode: bool = True,
    ) -> None:
        self.serial_port = serial_port
        self.baud_rate = baud_rate
        self.monitor_endpoint = monitor_endpoint
        self.mock_mode = mock_mode
        self._serial_connection = None
        self._socket_connection: Optional[socket.socket] = None
        self._socket_buffer = b""
        self._mock_distance_cm = 190.0
        self._mock_uptime_ms = 0
        self._resolved_serial_port: Optional[str] = None
        self._resolved_transport: Optional[str] = None

        if not self.mock_mode:
            self._connect_serial()

    @property
    def resolved_serial_port(self) -> Optional[str]:
        """Return the effective serial device path currently in use."""
        return self._resolved_serial_port

    @property
    def resolved_transport(self) -> Optional[str]:
        """Return effective live transport endpoint (serial or TCP)."""
        return self._resolved_transport

    def _monitor_endpoint(self) -> str:
        if self.monitor_endpoint is not None and str(self.monitor_endpoint).strip():
            return str(self.monitor_endpoint).strip()
        return str(os.getenv("RG_MONITOR_ENDPOINT", "tcp://127.0.0.1:7500")).strip()

    def _candidate_serial_ports(self) -> list[str]:
        """Build candidate serial device paths for Linux targets."""
        candidates: list[str] = []

        env_hint = os.getenv("RG_SERIAL_PORT_HINT", "").strip()
        if env_hint:
            candidates.append(env_hint)

        explicit = (self.serial_port or "").strip() if self.serial_port is not None else ""
        if explicit and explicit.upper() != "AUTO":
            candidates.append(explicit)

        for path in (
            "/dev/ttyACM0",
            "/dev/ttyACM1",
            "/dev/ttyUSB0",
            "/dev/ttyUSB1",
            "/dev/ttyUSB2",
            "/dev/ttyUSB3",
            "/dev/ttyUSB4",
            "/dev/ttyUSB5",
            "/dev/ttyUSB6",
            "/dev/ttyHS1",
            "/dev/ttyMSM0",
            "/dev/ttyS0",
            "/dev/ttyS1",
            "/dev/ttyS2",
            "/dev/ttyS3",
        ):
            if path not in candidates:
                candidates.append(path)

        return candidates

    def _looks_like_sensor_packet(self, packet: dict[str, Any]) -> bool:
        if not isinstance(packet, dict):
            return False

        required = {"node_id", "uptime_ms", "sensor_status"}
        if not required.issubset(packet.keys()):
            return False

        return "distance_cm" in packet or "error" in packet

    def _probe_port(self, port: str) -> bool:
        """Return True if the port emits expected sensor JSON packets."""
        try:
            import serial  # type: ignore

            with serial.Serial(port, self.baud_rate, timeout=1) as conn:
                for _ in range(8):
                    raw_line = conn.readline().decode("utf-8", errors="replace").strip()
                    if not raw_line:
                        continue
                    try:
                        packet = json.loads(raw_line)
                    except json.JSONDecodeError:
                        continue
                    if self._looks_like_sensor_packet(packet):
                        return True
        except Exception:
            return False

        return False

    def _probe_monitor_endpoint(self, endpoint: str) -> bool:
        """Return True if monitor endpoint emits expected sensor JSON packets."""
        try:
            if not endpoint.startswith("tcp://"):
                return False

            host_port = endpoint[len("tcp://") :]
            host, port_str = host_port.rsplit(":", 1)
            port = int(port_str)

            conn = socket.create_connection((host, port), timeout=3)
            conn.settimeout(1.5)
            buffer = b""
            started = time.time()

            while time.time() - started < 6:
                try:
                    data = conn.recv(4096)
                except socket.timeout:
                    continue
                if not data:
                    break
                buffer += data
                while b"\n" in buffer:
                    raw, buffer = buffer.split(b"\n", 1)
                    line = raw.decode("utf-8", errors="replace").strip()
                    if not line:
                        continue
                    try:
                        packet = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if self._looks_like_sensor_packet(packet):
                        conn.close()
                        return True

            conn.close()
            return False
        except Exception:
            return False

    def _connect_monitor_endpoint(self, endpoint: str) -> None:
        if not endpoint.startswith("tcp://"):
            raise ValueError(f"Unsupported monitor endpoint format: {endpoint}")

        host_port = endpoint[len("tcp://") :]
        host, port_str = host_port.rsplit(":", 1)
        port = int(port_str)

        conn = socket.create_connection((host, port), timeout=5)
        conn.settimeout(2)
        self._socket_connection = conn
        self._socket_buffer = b""

    def _connect_serial(self) -> None:
        """Open serial connection to Arduino sensor node."""
        try:
            desired = (self.serial_port or "").strip() if self.serial_port is not None else ""
            monitor_endpoint = self._monitor_endpoint()

            if not desired or desired.upper() == "AUTO":
                if self._probe_monitor_endpoint(monitor_endpoint):
                    self._connect_monitor_endpoint(monitor_endpoint)
                    self._resolved_transport = monitor_endpoint
                    self._resolved_serial_port = None
                    logging.info("Bridge connected on monitor endpoint: %s", monitor_endpoint)
                    return

            if desired.startswith("tcp://"):
                self._connect_monitor_endpoint(desired)
                self._resolved_transport = desired
                self._resolved_serial_port = None
                logging.info("Bridge connected on monitor endpoint: %s", desired)
                return

            import serial  # type: ignore

            if not desired or desired.upper() == "AUTO":
                selected_port = None
                for port in self._candidate_serial_ports():
                    if self._probe_port(port):
                        selected_port = port
                        break

                if selected_port is None:
                    raise RuntimeError(
                        "No sensor serial stream detected. Tried: "
                        + ", ".join(self._candidate_serial_ports())
                    )

                self._resolved_serial_port = selected_port
            else:
                self._resolved_serial_port = desired

            self._serial_connection = serial.Serial(
                self._resolved_serial_port,
                self.baud_rate,
                timeout=2,
            )

            time.sleep(2)
            self._resolved_transport = self._resolved_serial_port
            logging.info("Bridge connected on serial port: %s", self._resolved_serial_port)

        except Exception as exc:
            raise RuntimeError(f"Failed to open serial connection: {exc}") from exc

    def read_packet(self) -> SensorPacket:
        """Read one validated packet from either mock source or serial source."""
        if self.mock_mode:
            raw_packet = self._generate_mock_packet()
        else:
            raw_packet = self._read_live_json_line()

        return self._validate_packet(raw_packet)

    def _read_live_json_line(self) -> dict[str, Any]:
        """Read one JSON line from active live transport and parse it."""
        if self._socket_connection is not None:
            deadline = time.time() + 5
            while time.time() < deadline:
                while b"\n" in self._socket_buffer:
                    raw, self._socket_buffer = self._socket_buffer.split(b"\n", 1)
                    raw_line = raw.decode("utf-8", errors="replace").strip()
                    if raw_line:
                        try:
                            return json.loads(raw_line)
                        except json.JSONDecodeError as exc:
                            raise ValueError(
                                f"Invalid JSON from monitor endpoint: {raw_line}"
                            ) from exc

                try:
                    data = self._socket_connection.recv(4096)
                except socket.timeout:
                    continue

                if not data:
                    raise RuntimeError("Monitor endpoint closed the connection.")

                self._socket_buffer += data

            raise ValueError("Received empty monitor stream within timeout.")

        if self._serial_connection is None:
            raise RuntimeError("Serial connection is not initialized.")

        raw_line = self._serial_connection.readline().decode("utf-8", errors="replace").strip()

        if not raw_line:
            raise ValueError("Received empty serial line.")

        try:
            return json.loads(raw_line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON from Arduino: {raw_line}") from exc

    def _generate_mock_packet(self) -> dict[str, Any]:
        """
        Generate a realistic mock packet.

        This allows VS Code development before connecting the real UNO Q.
        """
        self._mock_uptime_ms += 3000

        # Simulate slowly rising water by decreasing sensor-to-water distance.
        self._mock_distance_cm -= 0.03

        value = round(self._mock_distance_cm, 2)
        return {
            "node_id": "UB-01",
            "uptime_ms": self._mock_uptime_ms,
            "distance_cm": value,
            "raw_distance_cm": value,
            "accepted_distance_cm": value,
            "candidate_distance_cm": value,
            "packet_sequence": self._mock_uptime_ms // 3000,
            "fw_profile": "MOCK",
            "fw_build": "mock",
            "valid_samples": 3,
            "failed_samples": 0,
            "sensor_status": "OK",
            "measurement_state": "OK",
        }

    def close(self) -> None:
        """Close active live connections if open."""
        if self._serial_connection is not None:
            try:
                self._serial_connection.close()
            except Exception:
                pass
            finally:
                self._serial_connection = None

        if self._socket_connection is not None:
            try:
                self._socket_connection.close()
            except Exception:
                pass
            finally:
                self._socket_connection = None
                self._socket_buffer = b""

    def _validate_packet(self, packet: dict[str, Any]) -> SensorPacket:
        """Validate raw packet and return strongly typed SensorPacket."""
        received_time_s = time.time()

        node_id = str(packet.get("node_id", "UNKNOWN"))
        uptime_ms = int(packet.get("uptime_ms", 0))
        valid_samples = int(packet.get("valid_samples", 0))
        failed_samples = int(packet.get("failed_samples", 0))
        sensor_status = str(packet.get("sensor_status", "UNKNOWN"))
        measurement_state = str(packet.get("measurement_state", sensor_status))
        error = packet.get("error")
        packet_sequence = packet.get("packet_sequence")
        fw_profile = packet.get("fw_profile")
        fw_build = packet.get("fw_build")

        raw_distance_value = packet.get("raw_distance_cm", packet.get("distance_cm"))
        accepted_distance_value = packet.get("accepted_distance_cm", packet.get("distance_cm"))
        candidate_distance_value = packet.get("candidate_distance_cm", raw_distance_value)
        distance_value = packet.get("distance_cm")

        def _to_float_or_none(value: Any) -> Optional[float]:
            if value is None:
                return None
            return float(value)

        if sensor_status != "OK":
            return SensorPacket(
                node_id=node_id,
                uptime_ms=uptime_ms,
                distance_cm=None,
                raw_distance_cm=_to_float_or_none(raw_distance_value),
                accepted_distance_cm=_to_float_or_none(accepted_distance_value),
                candidate_distance_cm=_to_float_or_none(candidate_distance_value),
                packet_sequence=int(packet_sequence) if packet_sequence is not None else None,
                fw_profile=str(fw_profile) if fw_profile is not None else None,
                fw_build=str(fw_build) if fw_build is not None else None,
                valid_samples=valid_samples,
                failed_samples=failed_samples,
                sensor_status=sensor_status,
                measurement_state=measurement_state,
                received_time_s=received_time_s,
                error=str(error) if error else "UNKNOWN_SENSOR_ERROR",
            )

        if distance_value is None:
            return SensorPacket(
                node_id=node_id,
                uptime_ms=uptime_ms,
                distance_cm=None,
                raw_distance_cm=_to_float_or_none(raw_distance_value),
                accepted_distance_cm=_to_float_or_none(accepted_distance_value),
                candidate_distance_cm=_to_float_or_none(candidate_distance_value),
                packet_sequence=int(packet_sequence) if packet_sequence is not None else None,
                fw_profile=str(fw_profile) if fw_profile is not None else None,
                fw_build=str(fw_build) if fw_build is not None else None,
                valid_samples=valid_samples,
                failed_samples=failed_samples,
                sensor_status="FAULT",
                measurement_state=measurement_state,
                received_time_s=received_time_s,
                error="MISSING_DISTANCE_CM",
            )

        distance_cm = float(distance_value)

        if distance_cm < 50 or distance_cm > 1500:
            return SensorPacket(
                node_id=node_id,
                uptime_ms=uptime_ms,
                distance_cm=None,
                raw_distance_cm=_to_float_or_none(raw_distance_value),
                accepted_distance_cm=_to_float_or_none(accepted_distance_value),
                candidate_distance_cm=_to_float_or_none(candidate_distance_value),
                packet_sequence=int(packet_sequence) if packet_sequence is not None else None,
                fw_profile=str(fw_profile) if fw_profile is not None else None,
                fw_build=str(fw_build) if fw_build is not None else None,
                valid_samples=valid_samples,
                failed_samples=failed_samples,
                sensor_status="FAULT",
                measurement_state=measurement_state,
                received_time_s=received_time_s,
                error="DISTANCE_OUT_OF_RANGE",
            )

        return SensorPacket(
            node_id=node_id,
            uptime_ms=uptime_ms,
            distance_cm=distance_cm,
            raw_distance_cm=_to_float_or_none(raw_distance_value),
            accepted_distance_cm=_to_float_or_none(accepted_distance_value),
            candidate_distance_cm=_to_float_or_none(candidate_distance_value),
            packet_sequence=int(packet_sequence) if packet_sequence is not None else None,
            fw_profile=str(fw_profile) if fw_profile is not None else None,
            fw_build=str(fw_build) if fw_build is not None else None,
            valid_samples=valid_samples,
            failed_samples=failed_samples,
            sensor_status=sensor_status,
            measurement_state=measurement_state,
            received_time_s=received_time_s,
            error=None,
        )
    