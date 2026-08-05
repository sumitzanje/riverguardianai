"""
RiverGuardian AI
Module 5: Weather-Aware Risk Fusion Engine

Purpose:
    Fuse river-risk output from risk_engine.py with weather observations
    from weather_fetcher.py.

This module does NOT replace the risk engine.
It upgrades the base river-only risk into a rainfall-aware fused risk.

Inputs:
    - RiskResult from risk_engine.py
    - WeatherPacket from weather_fetcher.py

Output:
    - FusedRiskResult
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import Any, Optional


RISK_ORDER = {
    "GREEN": 0,
    "YELLOW": 1,
    "ORANGE": 2,
    "RED": 3,
    "UNKNOWN": -1,
}


@dataclass
class FusedRiskResult:
    node_id: str
    base_risk: str
    fused_risk: str
    clearance_cm: float
    rise_rate_cm_min: float
    time_to_unsafe_min: Optional[float]
    rain_hourly_mm: Optional[float]
    rain_daily_mm: Optional[float]
    rainfall_class: str
    weather_influence: str
    recommendation_hint: str
    fusion_reason: str
    calculated_time_s: float

    def to_dict(self) -> dict[str, Any]:
        def _rounded_or_none(value: Optional[float], digits: int) -> Optional[float]:
            if value is None:
                return None
            return round(value, digits) if math.isfinite(value) else None

        return {
            "node_id": self.node_id,
            "base_risk": self.base_risk,
            "fused_risk": self.fused_risk,
            "clearance_cm": _rounded_or_none(self.clearance_cm, 2),
            "rise_rate_cm_min": _rounded_or_none(self.rise_rate_cm_min, 3),
            "time_to_unsafe_min": _rounded_or_none(self.time_to_unsafe_min, 2),
            "rain_hourly_mm": _rounded_or_none(self.rain_hourly_mm, 2),
            "rain_daily_mm": _rounded_or_none(self.rain_daily_mm, 2),
            "rainfall_class": self.rainfall_class,
            "weather_influence": self.weather_influence,
            "recommendation_hint": self.recommendation_hint,
            "fusion_reason": self.fusion_reason,
            "calculated_time_s": self.calculated_time_s,
        }


class WeatherFusionEngine:
    """
    Fuse river-only risk with rainfall/weather context.

    Design philosophy:
        - River condition remains primary.
        - Rainfall is used as an escalation/context signal.
        - Weather failure should not crash the safety system.
        - Fused risk should never be lower than base river risk.
    """

    def __init__(
        self,
        heavy_rain_hourly_mm: float = 10.0,
        intense_rain_hourly_mm: float = 20.0,
        extreme_rain_hourly_mm: float = 30.0,
        daily_saturation_mm: float = 50.0,
    ) -> None:
        self.heavy_rain_hourly_mm = heavy_rain_hourly_mm
        self.intense_rain_hourly_mm = intense_rain_hourly_mm
        self.extreme_rain_hourly_mm = extreme_rain_hourly_mm
        self.daily_saturation_mm = daily_saturation_mm

    def fuse(self, risk_result: Any, weather_packet: Any) -> FusedRiskResult:
        base_risk = risk_result.risk
        fused_risk = base_risk

        rain_hourly_mm = weather_packet.rain_hourly_mm
        rain_daily_mm = weather_packet.rain_daily_mm

        rainfall_class = self._classify_rainfall(rain_hourly_mm)
        weather_influence = self._describe_weather_influence(
            weather_status=weather_packet.station_status,
            rain_hourly_mm=rain_hourly_mm,
            rain_daily_mm=rain_daily_mm,
        )

        fusion_reason = "Base river-risk decision retained."
        recommendation_hint = self._base_recommendation(base_risk)

        if weather_packet.station_status != "OK":
            return FusedRiskResult(
                node_id=risk_result.node_id,
                base_risk=base_risk,
                fused_risk=fused_risk,
                clearance_cm=risk_result.clearance_cm,
                rise_rate_cm_min=risk_result.rise_rate_cm_min,
                time_to_unsafe_min=risk_result.time_to_unsafe_min,
                rain_hourly_mm=rain_hourly_mm,
                rain_daily_mm=rain_daily_mm,
                rainfall_class="UNKNOWN",
                weather_influence="Weather data unavailable; using river-only risk.",
                recommendation_hint=recommendation_hint,
                fusion_reason="Weather station unavailable; no rainfall escalation applied.",
                calculated_time_s=time.time(),
            )

        # Escalation logic:
        # Case 1: base GREEN but heavy rainfall and river is rising.
        if (
            base_risk == "GREEN"
            and self._is_at_least(rainfall_class, "HEAVY")
            and risk_result.rise_rate_cm_min > 0.5
        ):
            fused_risk = self._max_risk(fused_risk, "YELLOW")
            fusion_reason = (
                "Risk upgraded because rainfall is heavy and river level is rising."
            )

        # Case 2: base YELLOW + heavy rainfall = ORANGE.
        if base_risk == "YELLOW" and self._is_at_least(rainfall_class, "HEAVY"):
            fused_risk = self._max_risk(fused_risk, "ORANGE")
            fusion_reason = (
                "Risk upgraded because rising river conditions coincide with heavy rainfall."
            )

        # Case 3: base ORANGE + intense rainfall and low clearance = stronger ORANGE.
        if (
            base_risk == "ORANGE"
            and self._is_at_least(rainfall_class, "INTENSE")
            and risk_result.clearance_cm <= 50
        ):
            fused_risk = self._max_risk(fused_risk, "ORANGE")
            fusion_reason = (
                "ORANGE risk reinforced by intense rainfall and reduced bridge clearance."
            )

        # Case 4: extreme rainfall + critically low clearance = RED.
        if (
            self._is_at_least(rainfall_class, "EXTREME")
            and risk_result.clearance_cm <= 30
        ):
            fused_risk = self._max_risk(fused_risk, "RED")
            fusion_reason = (
                "Risk upgraded to RED due to extreme rainfall and critically low clearance."
            )

        # Case 5: wet catchment effect from daily rainfall.
        if (
            rain_daily_mm is not None
            and rain_daily_mm >= self.daily_saturation_mm
            and base_risk == "YELLOW"
        ):
            fused_risk = self._max_risk(fused_risk, "ORANGE")
            fusion_reason = (
                "Risk upgraded because accumulated daily rainfall indicates saturated conditions."
            )

        recommendation_hint = self._base_recommendation(fused_risk)

        return FusedRiskResult(
            node_id=risk_result.node_id,
            base_risk=base_risk,
            fused_risk=fused_risk,
            clearance_cm=risk_result.clearance_cm,
            rise_rate_cm_min=risk_result.rise_rate_cm_min,
            time_to_unsafe_min=risk_result.time_to_unsafe_min,
            rain_hourly_mm=rain_hourly_mm,
            rain_daily_mm=rain_daily_mm,
            rainfall_class=rainfall_class,
            weather_influence=weather_influence,
            recommendation_hint=recommendation_hint,
            fusion_reason=fusion_reason,
            calculated_time_s=time.time(),
        )

    def _classify_rainfall(self, rain_hourly_mm: Optional[float]) -> str:
        if rain_hourly_mm is None:
            return "UNKNOWN"

        if rain_hourly_mm >= self.extreme_rain_hourly_mm:
            return "EXTREME"

        if rain_hourly_mm >= self.intense_rain_hourly_mm:
            return "INTENSE"

        if rain_hourly_mm >= self.heavy_rain_hourly_mm:
            return "HEAVY"

        if rain_hourly_mm >= 2.0:
            return "MODERATE"

        if rain_hourly_mm > 0:
            return "LIGHT"

        return "NONE"

    def _describe_weather_influence(
        self,
        weather_status: str,
        rain_hourly_mm: Optional[float],
        rain_daily_mm: Optional[float],
    ) -> str:
        if weather_status != "OK":
            return "Weather station unavailable."

        if rain_hourly_mm is None:
            return "Rainfall data unavailable."

        if rain_hourly_mm == 0:
            return "No active rainfall forcing detected."

        if rain_hourly_mm < 2:
            return "Light rainfall detected."

        if rain_hourly_mm < self.heavy_rain_hourly_mm:
            return "Moderate rainfall may contribute to river response."

        if rain_hourly_mm < self.intense_rain_hourly_mm:
            return "Heavy rainfall may accelerate river rise."

        if rain_hourly_mm < self.extreme_rain_hourly_mm:
            return "Intense rainfall may rapidly worsen bridge conditions."

        return "Extreme rainfall detected; rapid flood response possible."

    def _base_recommendation(self, risk: str) -> str:
        if risk == "GREEN":
            return "Bridge currently appears safe. Continue monitoring."

        if risk == "YELLOW":
            return "Use caution. Monitor bridge conditions closely."

        if risk == "ORANGE":
            return "Avoid non-essential crossing. Prepare for possible unsafe conditions."

        if risk == "RED":
            return "Bridge unsafe. Do not cross."

        return "Risk unknown. Verify sensor and weather data."

    def _max_risk(self, risk_a: str, risk_b: str) -> str:
        return risk_a if RISK_ORDER.get(risk_a, -1) >= RISK_ORDER.get(risk_b, -1) else risk_b

    def _is_at_least(self, rainfall_class: str, threshold_class: str) -> bool:
        rainfall_order = {
            "UNKNOWN": -1,
            "NONE": 0,
            "LIGHT": 1,
            "MODERATE": 2,
            "HEAVY": 3,
            "INTENSE": 4,
            "EXTREME": 5,
        }

        return rainfall_order.get(rainfall_class, -1) >= rainfall_order.get(
            threshold_class,
            -1,
        )