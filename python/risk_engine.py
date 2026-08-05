"""
RiverGuardian AI
Module 3: Risk Engine

Purpose:
    Convert validated sensor packets into bridge flood-access intelligence.

Calculates:
    - bridge clearance
    - rise rate
    - rise acceleration
    - time to unsafe condition
    - risk level
"""

from __future__ import annotations

import math
import time
from collections import deque
from dataclasses import dataclass
from typing import Optional


@dataclass
class RiskResult:
    node_id: str
    distance_cm: float
    clearance_cm: float
    rise_rate_cm_min: float
    rise_acceleration_cm_min2: float
    time_to_unsafe_min: Optional[float]
    risk: str
    reason: str
    calculated_time_s: float

    def to_dict(self) -> dict:
        def _rounded_or_none(value: float, digits: int) -> Optional[float]:
            return round(value, digits) if math.isfinite(value) else None

        return {
            "node_id": self.node_id,
            "distance_cm": _rounded_or_none(self.distance_cm, 2),
            "clearance_cm": _rounded_or_none(self.clearance_cm, 2),
            "rise_rate_cm_min": round(self.rise_rate_cm_min, 3),
            "rise_acceleration_cm_min2": round(self.rise_acceleration_cm_min2, 3),
            "time_to_unsafe_min": round(self.time_to_unsafe_min, 2)
            if self.time_to_unsafe_min is not None
            else None,
            "risk": self.risk,
            "reason": self.reason,
            "calculated_time_s": self.calculated_time_s,
        }


class RiskEngine:
    def __init__(
        self,
        danger_distance_cm: float,
        critical_clearance_cm: float,
        orange_time_to_unsafe_min: float,
        yellow_time_to_unsafe_min: float,
        minimum_rise_rate_cm_min: float = 0.1,
        history_size: int = 8,
    ) -> None:
        self.danger_distance_cm = danger_distance_cm
        self.critical_clearance_cm = critical_clearance_cm
        self.orange_time_to_unsafe_min = orange_time_to_unsafe_min
        self.yellow_time_to_unsafe_min = yellow_time_to_unsafe_min
        self.minimum_rise_rate_cm_min = minimum_rise_rate_cm_min

        self.history: deque[tuple[float, float]] = deque(maxlen=history_size)
        self.previous_rise_rate_cm_min = 0.0
        self.previous_rise_rate_time_s: Optional[float] = None

    def evaluate(
        self,
        node_id: str,
        distance_cm: Optional[float],
        sensor_status: str,
        received_time_s: Optional[float] = None,
    ) -> RiskResult:
        now_s = received_time_s if received_time_s is not None else time.time()

        if sensor_status != "OK" or distance_cm is None:
            return RiskResult(
                node_id=node_id,
                distance_cm=float("nan"),
                clearance_cm=float("nan"),
                rise_rate_cm_min=0.0,
                rise_acceleration_cm_min2=0.0,
                time_to_unsafe_min=None,
                risk="UNKNOWN",
                reason="Sensor status is not OK; risk cannot be evaluated.",
                calculated_time_s=now_s,
            )

        clearance_cm = distance_cm - self.danger_distance_cm
        self.history.append((now_s, clearance_cm))

        rise_rate_cm_min = self._calculate_windowed_rise_rate()
        rise_acceleration_cm_min2 = self._calculate_acceleration(
            rise_rate_cm_min,
            now_s,
        )

        time_to_unsafe_min = self._calculate_time_to_unsafe(
            clearance_cm,
            rise_rate_cm_min,
        )

        risk, reason = self._classify_risk(
            clearance_cm,
            rise_rate_cm_min,
            time_to_unsafe_min,
        )

        self.previous_rise_rate_cm_min = rise_rate_cm_min
        self.previous_rise_rate_time_s = now_s

        return RiskResult(
            node_id=node_id,
            distance_cm=distance_cm,
            clearance_cm=clearance_cm,
            rise_rate_cm_min=rise_rate_cm_min,
            rise_acceleration_cm_min2=rise_acceleration_cm_min2,
            time_to_unsafe_min=time_to_unsafe_min,
            risk=risk,
            reason=reason,
            calculated_time_s=now_s,
        )

    def _calculate_windowed_rise_rate(self) -> float:
        if len(self.history) < 3:
            return 0.0

        oldest_time_s, oldest_clearance_cm = self.history[0]
        newest_time_s, newest_clearance_cm = self.history[-1]

        elapsed_min = (newest_time_s - oldest_time_s) / 60.0

        if elapsed_min <= 0:
            return 0.0

        clearance_drop_cm = oldest_clearance_cm - newest_clearance_cm
        rise_rate_cm_min = clearance_drop_cm / elapsed_min

        return max(0.0, rise_rate_cm_min)

    def _calculate_acceleration(
        self,
        current_rise_rate_cm_min: float,
        current_time_s: float,
    ) -> float:
        if self.previous_rise_rate_time_s is None:
            return 0.0

        elapsed_min = (current_time_s - self.previous_rise_rate_time_s) / 60.0
        if elapsed_min <= 0:
            return 0.0

        rate_delta = current_rise_rate_cm_min - self.previous_rise_rate_cm_min
        return rate_delta / elapsed_min

    def _calculate_time_to_unsafe(
        self,
        clearance_cm: float,
        rise_rate_cm_min: float,
    ) -> Optional[float]:
        if clearance_cm <= 0:
            return 0.0

        if rise_rate_cm_min < self.minimum_rise_rate_cm_min:
            return None

        return clearance_cm / rise_rate_cm_min

    def _classify_risk(
        self,
        clearance_cm: float,
        rise_rate_cm_min: float,
        time_to_unsafe_min: Optional[float],
    ) -> tuple[str, str]:
        if clearance_cm <= 0:
            return "RED", "Water has reached or exceeded unsafe bridge threshold."

        if clearance_cm <= self.critical_clearance_cm:
            return "RED", "Bridge clearance is critically low."

        if time_to_unsafe_min is not None:
            if time_to_unsafe_min <= self.orange_time_to_unsafe_min:
                return "ORANGE", "Water rise suggests unsafe bridge condition soon."

            if time_to_unsafe_min <= self.yellow_time_to_unsafe_min:
                return "YELLOW", "Water is rising; bridge should be monitored closely."

        if rise_rate_cm_min <= self.minimum_rise_rate_cm_min:
            return "GREEN", "Bridge is currently safe and no significant rise is detected."

        return "YELLOW", "Water is rising slowly."