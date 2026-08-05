"""
RiverGuardian AI
Main Uploader Test - Stage 10

Purpose:
    Test Modules 2 through 10 together.

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
        ↓
    ApiUploader
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
from api_uploader import ApiUploader


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

    # Current mode: MOCK.
    # Future mode: SUPABASE.
    uploader = ApiUploader(mode="MOCK")

    print("RiverGuardian AI - API Uploader Test Started")

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

        payload = uploader.build_payload(
            database_record_id=write_result.record_id,
            sensor_packet=sensor_packet,
            river_risk=river_risk,
            weather_packet=weather_packet,
            fused_result=fused_result,
            confidence=confidence,
            recommendation=recommendation,
            alert_decision=alert_decision,
        )

        upload_result = uploader.upload(payload)

        output = {
            "database_write": write_result.to_dict(),
            "cloud_payload_preview": {
                "node_id": payload["node_id"],
                "fused_risk": payload["fused_risk"],
                "confidence_score": payload["confidence_score"],
                "clearance_cm": payload["clearance_cm"],
                "rain_hourly_mm": payload["rain_hourly_mm"],
                "alert_should_send": payload["alert_should_send"],
            },
            "upload_result": upload_result.to_dict(),
        }

        print(json.dumps(output, indent=2, allow_nan=False))
        time.sleep(1)


if __name__ == "__main__":
    main()