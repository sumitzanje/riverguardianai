"""
RiverGuardian AI
Module 6: Confidence Engine

Purpose:
    Estimate reliability of the current fused flood-risk decision.

Inputs:
    - SensorPacket from bridge_interface.py
    - RiskResult from risk_engine.py
    - WeatherPacket from weather_fetcher.py
    - FusedRiskResult from weather_fusion_engine.py

Output:
    - ConfidenceResult
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import Any


@dataclass
class ConfidenceResult:
    confidence_score: int
    confidence_level: str
    confidence_reason: str
    sensor_score: int
    weather_score: int
    trend_score: int
    fusion_score: int
    calculated_time_s: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "confidence_score": self.confidence_score,
            "confidence_level": self.confidence_level,
            "confidence_reason": self.confidence_reason,
            "sensor_score": self.sensor_score,
            "weather_score": self.weather_score,
            "trend_score": self.trend_score,
            "fusion_score": self.fusion_score,
            "calculated_time_s": self.calculated_time_s,
        }


class ConfidenceEngine:
    """
    Confidence engine for RiverGuardian AI.

    Scoring philosophy:
        Sensor health is most important.
        Weather improves context.
        Trend stability improves prediction reliability.
        Fusion availability confirms full system operation.
    """

    def evaluate(
        self,
        sensor_packet: Any,
        risk_result: Any,
        weather_packet: Any,
        fused_result: Any,
    ) -> ConfidenceResult:
        sensor_score = self._score_sensor(sensor_packet)
        weather_score = self._score_weather(weather_packet)
        trend_score = self._score_trend(risk_result)
        fusion_score = self._score_fusion(fused_result)

        confidence_score = sensor_score + weather_score + trend_score + fusion_score
        confidence_score = max(0, min(100, confidence_score))

        confidence_level = self._classify_confidence(confidence_score)
        confidence_reason = self._build_reason(
            sensor_score,
            weather_score,
            trend_score,
            fusion_score,
            confidence_level,
        )

        return ConfidenceResult(
            confidence_score=confidence_score,
            confidence_level=confidence_level,
            confidence_reason=confidence_reason,
            sensor_score=sensor_score,
            weather_score=weather_score,
            trend_score=trend_score,
            fusion_score=fusion_score,
            calculated_time_s=time.time(),
        )

    def _score_sensor(self, sensor_packet: Any) -> int:
        if sensor_packet.sensor_status != "OK":
            return 0

        if sensor_packet.distance_cm is None:
            return 0

        valid = getattr(sensor_packet, "valid_samples", 0)
        failed = getattr(sensor_packet, "failed_samples", 0)

        if valid >= 3 and failed == 0:
            return 40

        if valid >= 2:
            return 30

        if valid == 1:
            return 15

        return 0

    def _score_weather(self, weather_packet: Any) -> int:
        if weather_packet.station_status != "OK":
            return 0

        if weather_packet.rain_hourly_mm is None:
            return 5

        return 20

    def _score_trend(self, risk_result: Any) -> int:
        rise_rate = getattr(risk_result, "rise_rate_cm_min", None)
        clearance = getattr(risk_result, "clearance_cm", None)

        if rise_rate is None or clearance is None:
            return 0

        if not math.isfinite(rise_rate) or not math.isfinite(clearance):
            return 0

        if rise_rate == 0:
            return 10

        if rise_rate > 0:
            return 20

        return 5

    def _score_fusion(self, fused_result: Any) -> int:
        if fused_result.fused_risk in {"GREEN", "YELLOW", "ORANGE", "RED"}:
            return 20

        return 0

    def _classify_confidence(self, score: int) -> str:
        if score >= 85:
            return "HIGH"

        if score >= 60:
            return "MEDIUM"

        if score >= 30:
            return "LOW"

        return "VERY_LOW"

    def _build_reason(
        self,
        sensor_score: int,
        weather_score: int,
        trend_score: int,
        fusion_score: int,
        confidence_level: str,
    ) -> str:
        reasons = []

        reasons.append(f"Confidence level is {confidence_level}.")

        if sensor_score >= 40:
            reasons.append("Sensor data is healthy.")
        elif sensor_score > 0:
            reasons.append("Sensor data is partially reliable.")
        else:
            reasons.append("Sensor data is unreliable.")

        if weather_score >= 20:
            reasons.append("Weather data is available.")
        elif weather_score > 0:
            reasons.append("Weather data is partially available.")
        else:
            reasons.append("Weather data is unavailable.")

        if trend_score >= 20:
            reasons.append("River trend is measurable.")
        elif trend_score >= 10:
            reasons.append("No significant river rise trend detected yet.")
        else:
            reasons.append("River trend is unreliable.")

        if fusion_score >= 20:
            reasons.append("Fusion engine produced a valid risk decision.")
        else:
            reasons.append("Fusion engine did not produce a valid decision.")

        return " ".join(reasons)