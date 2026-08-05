"""
RiverGuardian AI
Main Database Test - Stage 9

Purpose:
    Test Modules 2 through 9 together.

Pipeline:
    BridgeInterface
        ↓
    RiskEngine
        ↓
    WeatherFetcher
        ↓
    WeatherFusionEngine
        ↓
    ConfidenceEngine
        ↓
    RecommendationEngine
        ↓
    AlertManager
        ↓
    LocalDatabase
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from bridge_interface import BridgeInterface
from risk_engine import RiskEngine
from weather_fetcher import AmbientWeatherFetcher
from weather_fusion_engine import WeatherFusionEngine
from confidence_engine import ConfidenceEngine
from recommendation_engine import RecommendationEngine
from alert_manager import AlertManager
from local_database import LocalDatabase


def load_settings() -> dict:
    config_path = Path(__file__).resolve().parents[1] / "config" / "settings.json"

    with open(config_path, "r", encoding="utf-8") as file:
        return json.load(file)


def main() -> None:
    settings = load_settings()

    project_root = Path(__file__).resolve().parents[1]
    secrets_path = project_root / "config" / "ambient_weather_secrets.json"
    db_path = project_root / "data" / "riverguardian.db"

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
    confidence_engine = ConfidenceEngine()
    recommendation_engine = RecommendationEngine()
    alert_manager = AlertManager(
        orange_cooldown_s=10,
        red_cooldown_s=5,
        yellow_cooldown_s=20,
        send_yellow_alerts=False,
    )
    database = LocalDatabase(db_path)

    print("RiverGuardian AI - Local Database Test Started")

    for _ in range(10):
        sensor_packet = bridge.read_packet()

        river_risk = risk_engine.evaluate(
            node_id=sensor_packet.node_id,
            distance_cm=sensor_packet.distance_cm,
            sensor_status=sensor_packet.sensor_status,
            received_time_s=sensor_packet.received_time_s,
        )

        weather_packet = weather_fetcher.fetch_latest()
        fused_result = fusion_engine.fuse(river_risk, weather_packet)

        confidence = confidence_engine.evaluate(
            sensor_packet=sensor_packet,
            risk_result=river_risk,
            weather_packet=weather_packet,
            fused_result=fused_result,
        )

        recommendation = recommendation_engine.generate(
            fused_result=fused_result,
            confidence_result=confidence,
        )

        alert_decision = alert_manager.evaluate(recommendation)

        write_result = database.insert_monitoring_cycle(
            sensor_packet=sensor_packet,
            river_risk=river_risk,
            weather_packet=weather_packet,
            fused_result=fused_result,
            confidence=confidence,
            recommendation=recommendation,
            alert_decision=alert_decision,
        )

        output = {
            "fused_risk": fused_result.fused_risk,
            "confidence": confidence.confidence_score,
            "recommendation_status": recommendation.status,
            "alert_should_send": alert_decision.should_send,
            "database_write": write_result.to_dict(),
            "record_count": database.get_record_count(),
            "database_size_mb": database.get_database_size_mb(),
        }

        print(json.dumps(output, indent=2, allow_nan=False))
        time.sleep(1)

    latest_records = database.get_latest_records(limit=3)

    print("\nLatest 3 database records:")
    for record in latest_records:
        summary = {
            "id": record["id"],
            "node_id": record["node_id"],
            "fused_risk": record["fused_risk"],
            "clearance_cm": record["clearance_cm"],
            "rise_rate_cm_min": record["rise_rate_cm_min"],
            "rain_hourly_mm": record["rain_hourly_mm"],
            "confidence_score": record["confidence_score"],
            "recommendation_status": record["recommendation_status"],
            "alert_should_send": record["alert_should_send"],
        }
        print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()