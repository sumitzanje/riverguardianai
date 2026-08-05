"""
RiverGuardian AI
Module 7: Recommendation Engine

Purpose:
    Convert fused flood-risk and confidence outputs into actionable public-facing guidance.

Inputs:
    - FusedRiskResult from weather_fusion_engine.py
    - ConfidenceResult from confidence_engine.py

Output:
    - RecommendationResult
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class RecommendationResult:
    node_id: str
    status: str
    public_message: str
    technical_summary: str
    action_level: str
    send_whatsapp: bool
    dashboard_priority: str
    calculated_time_s: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "status": self.status,
            "public_message": self.public_message,
            "technical_summary": self.technical_summary,
            "action_level": self.action_level,
            "send_whatsapp": self.send_whatsapp,
            "dashboard_priority": self.dashboard_priority,
            "calculated_time_s": self.calculated_time_s,
        }


class RecommendationEngine:
    """
    Generates human-readable guidance from AI results.

    Design philosophy:
        - Keep public messages simple.
        - Avoid technical overload in village alerts.
        - Include technical summary for dashboard/reporting.
        - Do not send WhatsApp for every GREEN update.
    """

    def generate(
        self,
        fused_result: Any,
        confidence_result: Any,
    ) -> RecommendationResult:
        risk = fused_result.fused_risk
        confidence = confidence_result.confidence_level

        if risk == "GREEN":
            return self._green(fused_result, confidence)

        if risk == "YELLOW":
            return self._yellow(fused_result, confidence)

        if risk == "ORANGE":
            return self._orange(fused_result, confidence)

        if risk == "RED":
            return self._red(fused_result, confidence)

        return self._unknown(fused_result, confidence)

    def _green(self, fused_result: Any, confidence: str) -> RecommendationResult:
        public_message = (
            "RiverGuardian AI Update: The bridge currently appears safe. "
            "No significant flood risk is detected at this time."
        )

        technical_summary = self._technical_summary(fused_result, confidence)

        return RecommendationResult(
            node_id=fused_result.node_id,
            status="GREEN",
            public_message=public_message,
            technical_summary=technical_summary,
            action_level="NORMAL_MONITORING",
            send_whatsapp=False,
            dashboard_priority="LOW",
            calculated_time_s=time.time(),
        )

    def _yellow(self, fused_result: Any, confidence: str) -> RecommendationResult:
        public_message = (
            "RiverGuardian AI Caution: River level is rising near the bridge. "
            "The bridge appears passable now, but conditions should be monitored closely."
        )

        if fused_result.time_to_unsafe_min is not None:
            public_message += (
                f" Estimated time to unsafe level is approximately "
                f"{round(fused_result.time_to_unsafe_min)} minutes if the current trend continues."
            )

        technical_summary = self._technical_summary(fused_result, confidence)

        return RecommendationResult(
            node_id=fused_result.node_id,
            status="YELLOW",
            public_message=public_message,
            technical_summary=technical_summary,
            action_level="CAUTION",
            send_whatsapp=False,
            dashboard_priority="MEDIUM",
            calculated_time_s=time.time(),
        )

    def _orange(self, fused_result: Any, confidence: str) -> RecommendationResult:
        public_message = (
            "RiverGuardian AI Warning: Bridge conditions may become unsafe soon. "
            "Avoid non-essential travel toward the bridge."
        )

        if fused_result.time_to_unsafe_min is not None:
            public_message += (
                f" Estimated unsafe crossing time is approximately "
                f"{round(fused_result.time_to_unsafe_min)} minutes if the current trend continues."
            )

        technical_summary = self._technical_summary(fused_result, confidence)

        return RecommendationResult(
            node_id=fused_result.node_id,
            status="ORANGE",
            public_message=public_message,
            technical_summary=technical_summary,
            action_level="AVOID_NON_ESSENTIAL_CROSSING",
            send_whatsapp=True,
            dashboard_priority="HIGH",
            calculated_time_s=time.time(),
        )

    def _red(self, fused_result: Any, confidence: str) -> RecommendationResult:
        public_message = (
            "RiverGuardian AI Emergency Alert: The bridge is unsafe or very close to unsafe conditions. "
            "Do not attempt to cross the bridge."
        )

        technical_summary = self._technical_summary(fused_result, confidence)

        return RecommendationResult(
            node_id=fused_result.node_id,
            status="RED",
            public_message=public_message,
            technical_summary=technical_summary,
            action_level="DO_NOT_CROSS",
            send_whatsapp=True,
            dashboard_priority="CRITICAL",
            calculated_time_s=time.time(),
        )

    def _unknown(self, fused_result: Any, confidence: str) -> RecommendationResult:
        public_message = (
            "RiverGuardian AI Notice: Current bridge risk could not be confidently determined. "
            "Please verify local conditions before travel."
        )

        technical_summary = self._technical_summary(fused_result, confidence)

        return RecommendationResult(
            node_id=fused_result.node_id,
            status="UNKNOWN",
            public_message=public_message,
            technical_summary=technical_summary,
            action_level="VERIFY_CONDITIONS",
            send_whatsapp=True,
            dashboard_priority="HIGH",
            calculated_time_s=time.time(),
        )

    def _technical_summary(self, fused_result: Any, confidence: str) -> str:
        def _fmt_value(value: Optional[float], digits: int, suffix: str = "") -> str:
            if value is None:
                return "not available"
            if not math.isfinite(value):
                return "not available"
            return f"{round(value, digits)}{suffix}"

        time_text = (
            _fmt_value(fused_result.time_to_unsafe_min, 0, " min")
        )

        return (
            f"Risk={fused_result.fused_risk}; "
            f"BaseRisk={fused_result.base_risk}; "
            f"Clearance={_fmt_value(fused_result.clearance_cm, 1, ' cm')}; "
            f"RiseRate={_fmt_value(fused_result.rise_rate_cm_min, 2, ' cm/min')}; "
            f"TimeToUnsafe={time_text}; "
            f"RainHourly={_fmt_value(fused_result.rain_hourly_mm, 2, ' mm')}; "
            f"RainClass={fused_result.rainfall_class}; "
            f"Confidence={confidence}."
        )