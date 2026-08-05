"""
RiverGuardian AI
Main Application - Stage 3 Test

Purpose:
    Test Module 2 bridge_interface.py + Module 3 risk_engine.py.
"""

import json
import time
from pathlib import Path

from bridge_interface import BridgeInterface
from risk_engine import RiskEngine


def load_settings() -> dict:
    config_path = Path(__file__).resolve().parents[1] / "config" / "settings.json"

    with open(config_path, "r", encoding="utf-8") as file:
        return json.load(file)


def main() -> None:
    settings = load_settings()

    bridge = BridgeInterface(mock_mode=True)

    risk_engine = RiskEngine(
        danger_distance_cm=settings["danger_distance_cm"],
        critical_clearance_cm=settings["critical_clearance_cm"],
        orange_time_to_unsafe_min=settings["orange_time_to_unsafe_min"],
        yellow_time_to_unsafe_min=settings["yellow_time_to_unsafe_min"],
        minimum_rise_rate_cm_min=settings["minimum_rise_rate_cm_min"],
    )

    print("RiverGuardian AI - Risk Engine Test Started")

    for _ in range(12):
        packet = bridge.read_packet()

        result = risk_engine.evaluate(
            node_id=packet.node_id,
            distance_cm=packet.distance_cm,
            sensor_status=packet.sensor_status,
            received_time_s=packet.received_time_s,
        )

        print(json.dumps(result.to_dict(), indent=2, allow_nan=False))

        time.sleep(1)


if __name__ == "__main__":
    main()