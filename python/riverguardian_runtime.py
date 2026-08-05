"""
RiverGuardian AI
Canonical Production Runtime

Purpose:
    Run the full edge pipeline continuously on UNO Q Linux using real sensor data.

Pipeline:
    BridgeInterface -> RiskEngine -> WeatherFetcher -> WeatherFusionEngine
    -> ConfidenceEngine -> RecommendationEngine -> AlertManager
    -> LocalDatabase -> ApiUploader
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any

from alert_manager import AlertManager
from api_uploader import ApiUploader
from bridge_interface import BridgeInterface
from confidence_engine import ConfidenceEngine
from connectivity_manager import ConnectivityManager
from local_database import LocalDatabase
from recommendation_engine import RecommendationEngine
from risk_engine import RiskEngine
from runtime_config import load_runtime_settings
from weather_fetcher import AmbientWeatherFetcher
from weather_fusion_engine import WeatherFusionEngine


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def setup_logging(root: Path, level_name: str) -> None:
    logs_dir = root / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    log_file = logs_dir / "runtime.log"

    level = getattr(logging, level_name.upper(), logging.INFO)

    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)s | %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )


class RiverGuardianRuntime:
    """Unified production runtime controller."""

    def __init__(self) -> None:
        self.root = project_root()
        self.settings = load_runtime_settings(self.root)
        setup_logging(self.root, str(self.settings.get("log_level", "INFO")))
        self.secrets_path = self.root / "config" / "ambient_weather_secrets.json"
        self.db_path = self.root / "data" / "riverguardian.db"

        if not self.secrets_path.exists():
            raise FileNotFoundError(
                "Missing config/ambient_weather_secrets.json. "
                "Create it from config/ambient_weather_secrets.example.json"
            )

        self.mock_mode = bool(self.settings.get("mock_mode", False))
        self.serial_port = self.settings.get("serial_port")
        self.baud_rate = int(self.settings.get("baud_rate", 115200))
        self.modem_interface = str(self.settings.get("modem_interface", "")).strip()
        self.connectivity_health_url = str(
            self.settings.get("connectivity_health_url", "https://api.ipify.org")
        )
        self.connectivity_check_timeout_s = int(
            self.settings.get("connectivity_check_timeout_s", 5)
        )

        # Deployment safety guard: refuse to run with synthetic sensor data.
        if self.mock_mode:
            raise RuntimeError(
                "Deployment runtime requires real sensor data. "
                "Set mock_mode=false in config/settings.json"
            )

        self.monitoring_interval_s = float(
            self.settings.get("monitoring_interval_seconds", 30)
        )
        self.max_cycles = self.settings.get("max_runtime_cycles", None)

        self.bridge = BridgeInterface(
            mock_mode=self.mock_mode,
            serial_port=self.serial_port,
            baud_rate=self.baud_rate,
            monitor_endpoint=self.settings.get("monitor_endpoint"),
        )
        self.sensor_transport = self.bridge.resolved_transport or self.serial_port
        if self.bridge.resolved_serial_port:
            self.serial_port = self.bridge.resolved_serial_port

        self.risk_engine = RiskEngine(
            danger_distance_cm=self.settings["danger_distance_cm"],
            critical_clearance_cm=self.settings["critical_clearance_cm"],
            orange_time_to_unsafe_min=self.settings["orange_time_to_unsafe_min"],
            yellow_time_to_unsafe_min=self.settings["yellow_time_to_unsafe_min"],
            minimum_rise_rate_cm_min=self.settings["minimum_rise_rate_cm_min"],
        )

        self.weather_fetcher = AmbientWeatherFetcher(self.secrets_path)
        self.fusion_engine = WeatherFusionEngine()
        self.confidence_engine = ConfidenceEngine()
        self.recommendation_engine = RecommendationEngine()

        self.alert_manager = AlertManager(
            orange_cooldown_s=int(self.settings.get("orange_cooldown_s", 15 * 60)),
            red_cooldown_s=int(self.settings.get("red_cooldown_s", 5 * 60)),
            yellow_cooldown_s=int(self.settings.get("yellow_cooldown_s", 30 * 60)),
            send_yellow_alerts=bool(self.settings.get("send_yellow_alerts", False)),
        )

        self.database = LocalDatabase(self.db_path)

        self.connectivity_manager = ConnectivityManager(
            interface_name=self.modem_interface,
            health_url=self.connectivity_health_url,
            check_timeout_s=self.connectivity_check_timeout_s,
            at_port=str(self.settings.get("modem_at_port", "/dev/ttyUSB6")),
            at_baud=int(self.settings.get("modem_baud", 115200)),
            apn=str(self.settings.get("modem_apn", "www")),
            recovery_enabled=bool(self.settings.get("modem_recovery_enabled", True)),
            recovery_min_interval_s=int(
                self.settings.get("modem_recovery_min_interval_s", 20)
            ),
            recovery_max_interval_s=int(
                self.settings.get("modem_recovery_max_interval_s", 300)
            ),
            dhcp_timeout_s=int(self.settings.get("modem_dhcp_timeout_s", 25)),
        )

        self.uploader = ApiUploader(
            mode=str(self.settings.get("upload_mode", "MOCK")),
            endpoint=self.settings.get("upload_endpoint"),
            api_key=self.settings.get("upload_api_key"),
            table_name=str(
                self.settings.get("upload_table_name", "riverguardian_events")
            ),
        )

        self.cycle_count = 0

    def run_forever(self) -> None:
        logging.info("RiverGuardian AI runtime started.")
        logging.info("Device ID: %s", self.settings.get("device_id", "UNKNOWN"))
        logging.info("Site ID: %s", self.settings.get("site_id", "UNKNOWN"))
        logging.info("Sensor mode: REAL")
        logging.info("Sensor transport: %s", self.sensor_transport)
        logging.info("Modem interface: %s", self.modem_interface or "(not configured)")
        logging.info("Monitoring interval: %s seconds", self.monitoring_interval_s)

        try:
            while True:
                self.cycle_count += 1

                try:
                    cycle_output = self.run_one_cycle()
                except Exception as exc:
                    logging.exception("Cycle %s failed: %s", self.cycle_count, exc)
                    time.sleep(self.monitoring_interval_s)
                    continue

                logging.info(
                    "Cycle %s complete | risk=%s | confidence=%s | alert=%s | db_record=%s | upload=%s",
                    self.cycle_count,
                    cycle_output["fused_risk"],
                    cycle_output["confidence_score"],
                    cycle_output["alert_should_send"],
                    cycle_output["database_record_id"],
                    cycle_output["upload_success"],
                )

                print(json.dumps(cycle_output, indent=2, allow_nan=False))

                if self.max_cycles is not None and self.cycle_count >= int(self.max_cycles):
                    logging.info("Max runtime cycles reached. Runtime exiting normally.")
                    break

                time.sleep(self.monitoring_interval_s)

        except KeyboardInterrupt:
            logging.info("Runtime stopped by user.")

        finally:
            self.bridge.close()

    def run_one_cycle(self) -> dict[str, Any]:
        connectivity = self.connectivity_manager.check()
        if not connectivity.internet_ok:
            logging.warning(
                "Connectivity degraded | iface=%s exists=%s up=%s ipv4=%s reason=%s",
                connectivity.interface_name,
                connectivity.interface_exists,
                connectivity.lower_up,
                connectivity.has_ipv4,
                connectivity.reason,
            )

        sensor_packet = self.bridge.read_packet()

        river_risk = self.risk_engine.evaluate(
            node_id=sensor_packet.node_id,
            distance_cm=sensor_packet.distance_cm,
            sensor_status=sensor_packet.sensor_status,
            received_time_s=sensor_packet.received_time_s,
        )

        weather_packet = self.weather_fetcher.fetch_latest()
        fused_result = self.fusion_engine.fuse(river_risk, weather_packet)

        confidence = self.confidence_engine.evaluate(
            sensor_packet=sensor_packet,
            risk_result=river_risk,
            weather_packet=weather_packet,
            fused_result=fused_result,
        )

        recommendation = self.recommendation_engine.generate(
            fused_result=fused_result,
            confidence_result=confidence,
        )

        alert_decision = self.alert_manager.evaluate(recommendation)

        write_result = self.database.insert_monitoring_cycle(
            sensor_packet=sensor_packet,
            river_risk=river_risk,
            weather_packet=weather_packet,
            fused_result=fused_result,
            confidence=confidence,
            recommendation=recommendation,
            alert_decision=alert_decision,
        )

        payload = self.uploader.build_payload(
            database_record_id=write_result.record_id,
            device_id=str(self.settings.get("device_id", self.settings.get("node_id", "UNKNOWN"))),
            site_id=str(self.settings.get("site_id", "UNKNOWN")),
            sensor_packet=sensor_packet,
            river_risk=river_risk,
            weather_packet=weather_packet,
            fused_result=fused_result,
            confidence=confidence,
            recommendation=recommendation,
            alert_decision=alert_decision,
        )

        upload_result = self.uploader.upload(payload)

        return {
            "cycle": self.cycle_count,
            "device_id": str(self.settings.get("device_id", self.settings.get("node_id", "UNKNOWN"))),
            "site_id": str(self.settings.get("site_id", "UNKNOWN")),
            "node_id": fused_result.node_id,
            "distance_cm": sensor_packet.distance_cm,
            "raw_distance_cm": sensor_packet.raw_distance_cm,
            "accepted_distance_cm": sensor_packet.accepted_distance_cm,
            "candidate_distance_cm": sensor_packet.candidate_distance_cm,
            "sensor_status": sensor_packet.sensor_status,
            "measurement_state": sensor_packet.measurement_state,
            "sensor_error": sensor_packet.error,
            "packet_sequence": sensor_packet.packet_sequence,
            "fw_profile": sensor_packet.fw_profile,
            "fw_build": sensor_packet.fw_build,
            "connectivity": connectivity.to_dict(),
            "fused_risk": fused_result.fused_risk,
            "base_risk": fused_result.base_risk,
            "clearance_cm": fused_result.clearance_cm,
            "rise_rate_cm_min": fused_result.rise_rate_cm_min,
            "time_to_unsafe_min": fused_result.time_to_unsafe_min,
            "rain_hourly_mm": fused_result.rain_hourly_mm,
            "rainfall_class": fused_result.rainfall_class,
            "confidence_score": confidence.confidence_score,
            "confidence_level": confidence.confidence_level,
            "recommendation_status": recommendation.status,
            "public_message": recommendation.public_message,
            "alert_should_send": alert_decision.should_send,
            "alert_type": alert_decision.alert_type,
            "database_success": write_result.success,
            "database_record_id": write_result.record_id,
            "upload_success": upload_result.upload_success,
            "upload_mode": upload_result.upload_mode,
            "upload_error": upload_result.error,
            "telegram_enabled": bool(self.settings.get("telegram_enabled", False)),
            "telegram_configured": bool(self.settings.get("telegram_bot_token"))
            and bool(self.settings.get("telegram_chat_id")),
            "alert_notifier_poll_seconds": int(
                self.settings.get("alert_notifier_poll_seconds", 12)
            ),
        }


def main() -> None:
    runtime = RiverGuardianRuntime()
    runtime.run_forever()


if __name__ == "__main__":
    main()
