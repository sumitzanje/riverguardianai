"""
RiverGuardian AI
Module 9: Local SQLite Database Layer

Purpose:
    Store RiverGuardian AI monitoring cycles locally on the UNO Q Linux side.

Why:
    - Supports offline operation during 4G/cloud failure.
    - Preserves event history for dashboard plots.
    - Creates training data for future ML models.
    - Provides evidence for alerts and competition demonstration.

Storage:
    SQLite database with WAL mode.
"""

from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional


@dataclass
class DatabaseWriteResult:
    success: bool
    record_id: Optional[int]
    message: str
    calculated_time_s: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "record_id": self.record_id,
            "message": self.message,
            "calculated_time_s": self.calculated_time_s,
        }


class LocalDatabase:
    """
    SQLite database manager for RiverGuardian AI.

    Uses WAL mode for safer writes during continuous logging.
    """

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._initialize_database()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row

        connection.execute("PRAGMA journal_mode=WAL;")
        connection.execute("PRAGMA synchronous=NORMAL;")
        connection.execute("PRAGMA foreign_keys=ON;")

        return connection

    def _initialize_database(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS monitoring_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_time_s REAL NOT NULL,

                    node_id TEXT NOT NULL,

                    distance_cm REAL,
                    raw_distance_cm REAL,
                    accepted_distance_cm REAL,
                    candidate_distance_cm REAL,
                    packet_sequence INTEGER,
                    fw_profile TEXT,
                    fw_build TEXT,
                    sensor_status TEXT,
                    measurement_state TEXT,
                    sensor_error TEXT,
                    clearance_cm REAL,
                    rise_rate_cm_min REAL,
                    rise_acceleration_cm_min2 REAL,
                    time_to_unsafe_min REAL,

                    base_risk TEXT,
                    fused_risk TEXT,
                    rainfall_class TEXT,

                    rain_hourly_mm REAL,
                    rain_daily_mm REAL,
                    temp_c REAL,
                    humidity_percent REAL,
                    pressure_hpa REAL,
                    windspeed_kmh REAL,

                    confidence_score INTEGER,
                    confidence_level TEXT,

                    recommendation_status TEXT,
                    public_message TEXT,
                    action_level TEXT,
                    send_whatsapp INTEGER,
                    dashboard_priority TEXT,

                    alert_should_send INTEGER,
                    alert_type TEXT,
                    alert_reason TEXT,

                    raw_json TEXT NOT NULL
                );
                """
            )

            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_monitoring_created_time
                ON monitoring_records(created_time_s);
                """
            )

            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_monitoring_risk
                ON monitoring_records(fused_risk);
                """
            )

            for statement in (
                "ALTER TABLE monitoring_records ADD COLUMN raw_distance_cm REAL",
                "ALTER TABLE monitoring_records ADD COLUMN accepted_distance_cm REAL",
                "ALTER TABLE monitoring_records ADD COLUMN candidate_distance_cm REAL",
                "ALTER TABLE monitoring_records ADD COLUMN packet_sequence INTEGER",
                "ALTER TABLE monitoring_records ADD COLUMN fw_profile TEXT",
                "ALTER TABLE monitoring_records ADD COLUMN fw_build TEXT",
                "ALTER TABLE monitoring_records ADD COLUMN sensor_status TEXT",
                "ALTER TABLE monitoring_records ADD COLUMN measurement_state TEXT",
                "ALTER TABLE monitoring_records ADD COLUMN sensor_error TEXT",
            ):
                try:
                    connection.execute(statement)
                except sqlite3.OperationalError:
                    pass

    def insert_monitoring_cycle(
        self,
        *,
        sensor_packet: Any,
        river_risk: Any,
        weather_packet: Any,
        fused_result: Any,
        confidence: Any,
        recommendation: Any,
        alert_decision: Any,
    ) -> DatabaseWriteResult:
        """
        Store one full monitoring cycle.
        """

        now_s = time.time()

        raw_payload = {
            "sensor_packet": self._safe_to_dict(sensor_packet),
            "river_risk": self._safe_to_dict(river_risk),
            "weather": self._safe_to_dict(weather_packet),
            "fused_result": self._safe_to_dict(fused_result),
            "confidence": self._safe_to_dict(confidence),
            "recommendation": self._safe_to_dict(recommendation),
            "alert_decision": self._safe_to_dict(alert_decision),
        }

        try:
            with self._connect() as connection:
                cursor = connection.execute(
                    """
                    INSERT INTO monitoring_records (
                        created_time_s,
                        node_id,

                        distance_cm,
                        raw_distance_cm,
                        accepted_distance_cm,
                        candidate_distance_cm,
                        packet_sequence,
                        fw_profile,
                        fw_build,
                        sensor_status,
                        measurement_state,
                        sensor_error,
                        clearance_cm,
                        rise_rate_cm_min,
                        rise_acceleration_cm_min2,
                        time_to_unsafe_min,

                        base_risk,
                        fused_risk,
                        rainfall_class,

                        rain_hourly_mm,
                        rain_daily_mm,
                        temp_c,
                        humidity_percent,
                        pressure_hpa,
                        windspeed_kmh,

                        confidence_score,
                        confidence_level,

                        recommendation_status,
                        public_message,
                        action_level,
                        send_whatsapp,
                        dashboard_priority,

                        alert_should_send,
                        alert_type,
                        alert_reason,

                        raw_json
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """,
                    (
                        now_s,
                        getattr(fused_result, "node_id", "UNKNOWN"),

                        getattr(sensor_packet, "distance_cm", None),
                        getattr(sensor_packet, "raw_distance_cm", None),
                        getattr(sensor_packet, "accepted_distance_cm", None),
                        getattr(sensor_packet, "candidate_distance_cm", None),
                        getattr(sensor_packet, "packet_sequence", None),
                        getattr(sensor_packet, "fw_profile", None),
                        getattr(sensor_packet, "fw_build", None),
                        getattr(sensor_packet, "sensor_status", None),
                        getattr(sensor_packet, "measurement_state", None),
                        getattr(sensor_packet, "error", None),
                        getattr(fused_result, "clearance_cm", None),
                        getattr(fused_result, "rise_rate_cm_min", None),
                        getattr(river_risk, "rise_acceleration_cm_min2", None),
                        getattr(fused_result, "time_to_unsafe_min", None),

                        getattr(fused_result, "base_risk", None),
                        getattr(fused_result, "fused_risk", None),
                        getattr(fused_result, "rainfall_class", None),

                        getattr(weather_packet, "rain_hourly_mm", None),
                        getattr(weather_packet, "rain_daily_mm", None),
                        getattr(weather_packet, "temp_c", None),
                        getattr(weather_packet, "humidity_percent", None),
                        getattr(weather_packet, "pressure_hpa", None),
                        getattr(weather_packet, "windspeed_kmh", None),

                        getattr(confidence, "confidence_score", None),
                        getattr(confidence, "confidence_level", None),

                        getattr(recommendation, "status", None),
                        getattr(recommendation, "public_message", None),
                        getattr(recommendation, "action_level", None),
                        int(bool(getattr(recommendation, "send_whatsapp", False))),
                        getattr(recommendation, "dashboard_priority", None),

                        int(bool(getattr(alert_decision, "should_send", False))),
                        getattr(alert_decision, "alert_type", None),
                        getattr(alert_decision, "reason", None),

                        json.dumps(raw_payload, ensure_ascii=False),
                    ),
                )

                record_id = cursor.lastrowid

            return DatabaseWriteResult(
                success=True,
                record_id=record_id,
                message="Monitoring cycle stored successfully.",
                calculated_time_s=time.time(),
            )

        except Exception as exc:
            return DatabaseWriteResult(
                success=False,
                record_id=None,
                message=f"Database write failed: {exc}",
                calculated_time_s=time.time(),
            )

    def get_latest_records(self, limit: int = 10) -> list[dict[str, Any]]:
        """
        Return latest records for quick testing/dashboard use.
        """
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM monitoring_records
                ORDER BY created_time_s DESC
                LIMIT ?;
                """,
                (limit,),
            ).fetchall()

        return [dict(row) for row in rows]

    def get_record_count(self) -> int:
        """
        Return total number of stored records.
        """
        with self._connect() as connection:
            row = connection.execute(
                "SELECT COUNT(*) AS count FROM monitoring_records;"
            ).fetchone()

        return int(row["count"])

    def get_database_size_mb(self) -> float:
        """
        Return approximate database file size in MB.
        """
        if not self.db_path.exists():
            return 0.0

        return round(self.db_path.stat().st_size / (1024 * 1024), 3)

    @staticmethod
    def _safe_to_dict(obj: Any) -> dict[str, Any]:
        if hasattr(obj, "to_dict"):
            return obj.to_dict()

        if hasattr(obj, "__dict__"):
            return dict(obj.__dict__)

        return {"value": str(obj)}