"""
RiverGuardian AI
Module 10: API Uploader / Cloud Sync Stub

Purpose:
    Prepare and upload RiverGuardian AI outputs to an external cloud service.

Current mode:
    MOCK mode only.

Future mode:
    Supabase REST API upload.
"""

from __future__ import annotations

import json
import re
import time
from importlib import import_module
from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class UploadResult:
    upload_success: bool
    upload_mode: str
    endpoint: Optional[str]
    status_code: Optional[int]
    record_id: Optional[int]
    message: str
    error: Optional[str]
    calculated_time_s: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "upload_success": self.upload_success,
            "upload_mode": self.upload_mode,
            "endpoint": self.endpoint,
            "status_code": self.status_code,
            "record_id": self.record_id,
            "message": self.message,
            "error": self.error,
            "calculated_time_s": self.calculated_time_s,
        }


class ApiUploader:
    """
    Cloud uploader interface.

    Modes:
        MOCK:
            Simulates upload locally.

        SUPABASE:
            Future REST upload to Supabase table.
    """

    def __init__(
        self,
        mode: str = "MOCK",
        endpoint: Optional[str] = None,
        api_key: Optional[str] = None,
        table_name: str = "riverguardian_events",
        timeout_s: int = 10,
    ) -> None:
        self.mode = mode.upper()
        self.endpoint = endpoint
        self.api_key = api_key
        self.table_name = table_name
        self.timeout_s = timeout_s

    def build_payload(
        self,
        *,
        database_record_id: Optional[int],
        device_id: Optional[str],
        site_id: Optional[str],
        sensor_packet: Any,
        river_risk: Any,
        weather_packet: Any,
        fused_result: Any,
        confidence: Any,
        recommendation: Any,
        alert_decision: Any,
    ) -> dict[str, Any]:
        """
        Build a clean cloud payload.

        This payload is intentionally flatter than raw database JSON.
        It is dashboard/API friendly.
        """

        return {
            "local_record_id": database_record_id,
            "created_time_s": time.time(),

            "device_id": device_id,
            "site_id": site_id,
            "node_id": getattr(fused_result, "node_id", "UNKNOWN"),

            "distance_cm": getattr(sensor_packet, "distance_cm", None),
            "raw_distance_cm": getattr(sensor_packet, "raw_distance_cm", None),
            "accepted_distance_cm": getattr(sensor_packet, "accepted_distance_cm", None),
            "candidate_distance_cm": getattr(sensor_packet, "candidate_distance_cm", None),
            "sensor_status": getattr(sensor_packet, "sensor_status", None),
            "measurement_state": getattr(sensor_packet, "measurement_state", None),
            "sensor_error": getattr(sensor_packet, "error", None),
            "packet_sequence": getattr(sensor_packet, "packet_sequence", None),
            "fw_profile": getattr(sensor_packet, "fw_profile", None),
            "fw_build": getattr(sensor_packet, "fw_build", None),
            "clearance_cm": getattr(fused_result, "clearance_cm", None),
            "rise_rate_cm_min": getattr(fused_result, "rise_rate_cm_min", None),
            "rise_acceleration_cm_min2": getattr(
                river_risk,
                "rise_acceleration_cm_min2",
                None,
            ),
            "time_to_unsafe_min": getattr(fused_result, "time_to_unsafe_min", None),

            "base_risk": getattr(fused_result, "base_risk", None),
            "fused_risk": getattr(fused_result, "fused_risk", None),
            "rainfall_class": getattr(fused_result, "rainfall_class", None),

            "rain_hourly_mm": getattr(weather_packet, "rain_hourly_mm", None),
            "rain_daily_mm": getattr(weather_packet, "rain_daily_mm", None),
            "temp_c": getattr(weather_packet, "temp_c", None),
            "humidity_percent": getattr(weather_packet, "humidity_percent", None),
            "pressure_hpa": getattr(weather_packet, "pressure_hpa", None),
            "windspeed_kmh": getattr(weather_packet, "windspeed_kmh", None),

            "confidence_score": getattr(confidence, "confidence_score", None),
            "confidence_level": getattr(confidence, "confidence_level", None),

            "recommendation_status": getattr(recommendation, "status", None),
            "public_message": getattr(recommendation, "public_message", None),
            "technical_summary": getattr(recommendation, "technical_summary", None),
            "action_level": getattr(recommendation, "action_level", None),
            "send_whatsapp": bool(getattr(recommendation, "send_whatsapp", False)),
            "dashboard_priority": getattr(recommendation, "dashboard_priority", None),

            "alert_should_send": bool(getattr(alert_decision, "should_send", False)),
            "alert_type": getattr(alert_decision, "alert_type", None),
            "alert_reason": getattr(alert_decision, "reason", None),
            "alert_message": getattr(alert_decision, "message", None),
        }

    def upload(self, payload: dict[str, Any]) -> UploadResult:
        if self.mode == "MOCK":
            return self._mock_upload(payload)

        if self.mode == "SUPABASE":
            return self._supabase_upload(payload)

        return UploadResult(
            upload_success=False,
            upload_mode=self.mode,
            endpoint=self.endpoint,
            status_code=None,
            record_id=payload.get("local_record_id"),
            message="Unsupported upload mode.",
            error=f"Unknown uploader mode: {self.mode}",
            calculated_time_s=time.time(),
        )

    def _mock_upload(self, payload: dict[str, Any]) -> UploadResult:
        """
        Simulate cloud upload.

        This lets us test the pipeline before Supabase credentials exist.
        """
        required_fields = ["node_id", "fused_risk", "confidence_score"]

        missing = [field for field in required_fields if payload.get(field) is None]

        if missing:
            return UploadResult(
                upload_success=False,
                upload_mode="MOCK",
                endpoint=None,
                status_code=None,
                record_id=payload.get("local_record_id"),
                message="Mock upload failed because required fields are missing.",
                error=f"Missing fields: {missing}",
                calculated_time_s=time.time(),
            )

        return UploadResult(
            upload_success=True,
            upload_mode="MOCK",
            endpoint=None,
            status_code=200,
            record_id=payload.get("local_record_id"),
            message="Mock upload successful. Payload is cloud-ready.",
            error=None,
            calculated_time_s=time.time(),
        )

    def _supabase_upload(self, payload: dict[str, Any]) -> UploadResult:
        """
        Future Supabase upload.

        Required future config:
            endpoint = https://YOUR_PROJECT.supabase.co
            api_key = Supabase service role key or anon key with insert permission
            table_name = riverguardian_events
        """

        requests_module = self._requests_module()

        if requests_module is None:
            return UploadResult(
                upload_success=False,
                upload_mode="SUPABASE",
                endpoint=self.endpoint,
                status_code=None,
                record_id=payload.get("local_record_id"),
                message="Requests package not installed.",
                error="Install requests using: python -m pip install requests",
                calculated_time_s=time.time(),
            )

        if not self.endpoint or not self.api_key:
            return UploadResult(
                upload_success=False,
                upload_mode="SUPABASE",
                endpoint=self.endpoint,
                status_code=None,
                record_id=payload.get("local_record_id"),
                message="Supabase upload skipped because endpoint or API key is missing.",
                error="Missing Supabase endpoint/api_key.",
                calculated_time_s=time.time(),
            )

        url = f"{self.endpoint.rstrip('/')}/rest/v1/{self.table_name}"

        headers = {
            "apikey": self.api_key,
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal",
        }

        working_payload = dict(payload)
        dropped_columns: list[str] = []

        try:
            for _ in range(12):
                response = requests_module.post(
                    url,
                    headers=headers,
                    data=json.dumps(working_payload),
                    timeout=self.timeout_s,
                )

                success = 200 <= response.status_code < 300
                if success:
                    message = "Supabase upload successful."
                    if dropped_columns:
                        message = (
                            "Supabase upload successful after dropping unsupported columns: "
                            + ", ".join(dropped_columns)
                        )

                    return UploadResult(
                        upload_success=True,
                        upload_mode="SUPABASE",
                        endpoint=url,
                        status_code=response.status_code,
                        record_id=payload.get("local_record_id"),
                        message=message,
                        error=None,
                        calculated_time_s=time.time(),
                    )

                unsupported_column = self._extract_unsupported_column(response.text)
                if (
                    unsupported_column
                    and unsupported_column in working_payload
                    and unsupported_column not in dropped_columns
                ):
                    dropped_columns.append(unsupported_column)
                    working_payload.pop(unsupported_column, None)
                    continue

                return UploadResult(
                    upload_success=False,
                    upload_mode="SUPABASE",
                    endpoint=url,
                    status_code=response.status_code,
                    record_id=payload.get("local_record_id"),
                    message="Supabase upload failed.",
                    error=response.text,
                    calculated_time_s=time.time(),
                )

            return UploadResult(
                upload_success=False,
                upload_mode="SUPABASE",
                endpoint=url,
                status_code=None,
                record_id=payload.get("local_record_id"),
                message="Supabase upload failed after schema-compat retries.",
                error="Exceeded retry budget while removing unsupported columns.",
                calculated_time_s=time.time(),
            )

        except Exception as exc:
            return UploadResult(
                upload_success=False,
                upload_mode="SUPABASE",
                endpoint=url,
                status_code=None,
                record_id=payload.get("local_record_id"),
                message="Supabase upload exception.",
                error=str(exc),
                calculated_time_s=time.time(),
            )

    @staticmethod
    def _requests_module() -> Optional[Any]:
        try:
            return import_module("requests")
        except ModuleNotFoundError:
            return None

    @staticmethod
    def _extract_unsupported_column(response_text: str) -> Optional[str]:
        # PostgREST unknown-column errors often contain text like:
        # "Could not find the 'accepted_distance_cm' column of 'riverguardian_events' ..."
        match = re.search(r"'([^']+)' column", response_text or "")
        if not match:
            return None
        return match.group(1)