"""
RiverGuardian AI
Main Fusion Test - Stage 5

Purpose:
    Test Modules 2 + 3 + 4 + 5 together without modifying main.py.

Pipeline:
    BridgeInterface
        ↓
    RiskEngine
        ↓
    AmbientWeatherFetcher
        ↓
    WeatherFusionEngine
        ↓
    Console Output
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from bridge_interface import BridgeInterface
from risk_engine import RiskEngine
from weather_fetcher import AmbientWeatherFetcher
from weather_fusion_engine import WeatherFusionEngine


def load_settings() -> dict:
    config_path = Path(__file__).resolve().parents[1] / "config" / "settings.json"

    with open(config_path, "r", encoding="utf-8") as file:
        return json.load(file)


def main() -> None:
    settings = load_settings()

    secrets_path = (
        Path(__file__).resolve().parents[1]
        / "config"
        / "ambient_weather_secrets.json"
    )

    if not secrets_path.exists():
        raise FileNotFoundError(
            "Missing config/ambient_weather_secrets.json. "
            "Create it from config/ambient_weather_secrets.example.json"
        )

    bridge = BridgeInterface(mock_mode=True)

    risk_engine = RiskEngine(
        danger_distance_cm=settings["danger_distance_cm"],
        critical_clearance_cm=settings["critical_clearance_cm"],
        orange_time_to_unsafe_min=settings["orange_time_to_unsafe_min"],
        yellow_time_to_unsafe_min=settings["yellow_time_to_unsafe_min"],
        minimum_rise_rate_cm_min=settings["minimum_rise_rate_cm_min"],
    )

    weather_fetcher = AmbientWeatherFetcher(secrets_path)
    fusion_engine = WeatherFusionEngine()

    print("RiverGuardian AI - Weather Fusion Test Started")

    for _ in range(12):
        sensor_packet = bridge.read_packet()

        river_risk = risk_engine.evaluate(
            node_id=sensor_packet.node_id,
            distance_cm=sensor_packet.distance_cm,
            sensor_status=sensor_packet.sensor_status,
            received_time_s=sensor_packet.received_time_s,
        )

        weather_packet = weather_fetcher.fetch_latest()
        fused_result = fusion_engine.fuse(river_risk, weather_packet)

        combined_output = {
            "river_risk": river_risk.to_dict(),
            "weather": weather_packet.to_dict(),
            "fused_result": fused_result.to_dict(),
        }

        print(json.dumps(combined_output, indent=2, allow_nan=False))
        time.sleep(1)


if __name__ == "__main__":
    main()