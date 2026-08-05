"""
RiverGuardian AI
Module 2: Bridge Interface

Purpose:
    Read structured JSON packets from the Arduino/STM32 sensor layer and
    provide validated data to the Python edge-AI pipeline.

Modes:
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
import time
from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class SensorPacket:
    """Validated sensor packet from the Arduino sensor node."""

    node_id: str
    uptime_ms: int
    distance_cm: Optional[float]
    valid_samples: int
    failed_samples: int
    sensor_status: str
    received_time_s: float
    error: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert packet to dictionary for downstream modules."""
        return {
            "node_id": self.node_id,
            "uptime_ms": self.uptime_ms,
            "distance_cm": self.distance_cm,
            "valid_samples": self.valid_samples,
            "failed_samples": self.failed_samples,
            "sensor_status": self.sensor_status,
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
        mock_mode: bool = True,
    ) -> None:
        self.serial_port = serial_port
        self.baud_rate = baud_rate
        self.mock_mode = mock_mode
        self._serial_connection = None
        self._mock_distance_cm = 190.0
        self._mock_uptime_ms = 0

        if not self.mock_mode:
            self._connect_serial()

    def _connect_serial(self) -> None:
        """Open serial connection to Arduino sensor node."""
        try:
            import serial  # type: ignore

            if self.serial_port is None:
                raise ValueError("serial_port must be provided when mock_mode=False.")

            self._serial_connection = serial.Serial(
                self.serial_port,
                self.baud_rate,
                timeout=2,
            )

            time.sleep(2)

        except Exception as exc:
            raise RuntimeError(f"Failed to open serial connection: {exc}") from exc

    def close(self) -> None:
        """Close serial connection cleanly."""
        if self._serial_connection is not None:
            try:
                self._serial_connection.close()
            except Exception:
                pass
            finally:
                self._serial_connection = None

    def read_packet(self) -> SensorPacket:
        """Read one validated packet from either mock source or serial source."""
        if self.mock_mode:
            raw_packet = self._generate_mock_packet()
        else:
            raw_packet = self._read_serial_json_line()

        return self._validate_packet(raw_packet)

    def _read_serial_json_line(self) -> dict[str, Any]:
        """Read one JSON line from serial and parse it."""
        if self._serial_connection is None:
            raise RuntimeError("Serial connection is not initialized.")

        raw_line = self._serial_connection.readline().decode(
            "utf-8",
            errors="replace",
        ).strip()

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

        return {
            "node_id": "UB-01",
            "uptime_ms": self._mock_uptime_ms,
            "distance_cm": round(self._mock_distance_cm, 2),
            "valid_samples": 3,
            "failed_samples": 0,
            "sensor_status": "OK",
        }

    def _validate_packet(self, packet: dict[str, Any]) -> SensorPacket:
        """Validate raw packet and return strongly typed SensorPacket."""
        received_time_s = time.time()

        node_id = str(packet.get("node_id", "UNKNOWN"))
        uptime_ms = int(packet.get("uptime_ms", 0))
        valid_samples = int(packet.get("valid_samples", 0))
        failed_samples = int(packet.get("failed_samples", 0))
        sensor_status = str(packet.get("sensor_status", "UNKNOWN"))
        error = packet.get("error")

        distance_value = packet.get("distance_cm")

        if sensor_status != "OK":
            return SensorPacket(
                node_id=node_id,
                uptime_ms=uptime_ms,
                distance_cm=None,
                valid_samples=valid_samples,
                failed_samples=failed_samples,
                sensor_status=sensor_status,
                received_time_s=received_time_s,
                error=str(error) if error else "UNKNOWN_SENSOR_ERROR",
            )

        if distance_value is None:
            return SensorPacket(
                node_id=node_id,
                uptime_ms=uptime_ms,
                distance_cm=None,
                valid_samples=valid_samples,
                failed_samples=failed_samples,
                sensor_status="FAULT",
                received_time_s=received_time_s,
                error="MISSING_DISTANCE_CM",
            )

        distance_cm = float(distance_value)

        if distance_cm < 50 or distance_cm > 1500:
            return SensorPacket(
                node_id=node_id,
                uptime_ms=uptime_ms,
                distance_cm=None,
                valid_samples=valid_samples,
                failed_samples=failed_samples,
                sensor_status="FAULT",
                received_time_s=received_time_s,
                error="DISTANCE_OUT_OF_RANGE",
            )

        return SensorPacket(
            node_id=node_id,
            uptime_ms=uptime_ms,
            distance_cm=distance_cm,
            valid_samples=valid_samples,
            failed_samples=failed_samples,
            sensor_status=sensor_status,
            received_time_s=received_time_s,
            error=None,
        )


if __name__ == "__main__":
    USE_MOCK = False
    SERIAL_PORT = "COM5"
    BAUD_RATE = 115200

    bridge = None

    try:
        if USE_MOCK:
            print("Running in MOCK mode...")
            bridge = BridgeInterface(mock_mode=True)
        else:
            print(f"Running in SENSOR mode on {SERIAL_PORT} at {BAUD_RATE} baud...")
            bridge = BridgeInterface(
                serial_port=SERIAL_PORT,
                baud_rate=BAUD_RATE,
                mock_mode=False,
            )

        while True:
            packet = bridge.read_packet()
            print(packet.to_dict())
            time.sleep(1)

    except KeyboardInterrupt:
        print("\nStopped by user.")

    except Exception as exc:
        print(f"Runtime error: {exc}")

    finally:
        if bridge is not None:
            bridge.close()