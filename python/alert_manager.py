"""
RiverGuardian AI
Module 8: Alert Manager

Purpose:
    Decide when an alert should be sent and prevent repeated WhatsApp spam.

Inputs:
    - RecommendationResult from recommendation_engine.py

Output:
    - AlertDecision

Design goals:
    - Send alerts only when needed.
    - Always send ORANGE/RED escalation alerts.
    - Avoid repeated messages during same condition.
    - Send recovery message when system returns to safe/caution.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Optional


RISK_PRIORITY = {
    "UNKNOWN": -1,
    "GREEN": 0,
    "YELLOW": 1,
    "ORANGE": 2,
    "RED": 3,
}


@dataclass
class AlertDecision:
    node_id: str
    should_send: bool
    alert_type: str
    current_status: str
    previous_status: Optional[str]
    message: str
    reason: str
    calculated_time_s: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "should_send": self.should_send,
            "alert_type": self.alert_type,
            "current_status": self.current_status,
            "previous_status": self.previous_status,
            "message": self.message,
            "reason": self.reason,
            "calculated_time_s": self.calculated_time_s,
        }


class AlertManager:
    """
    Alert decision manager.

    This module does NOT send WhatsApp yet.
    It only decides whether an alert should be sent.

    Actual sending will happen later in:
        api_uploader.py / whatsapp_sender.py
    """

    def __init__(
        self,
        orange_cooldown_s: int = 15 * 60,
        red_cooldown_s: int = 5 * 60,
        yellow_cooldown_s: int = 30 * 60,
        send_yellow_alerts: bool = False,
    ) -> None:
        self.orange_cooldown_s = orange_cooldown_s
        self.red_cooldown_s = red_cooldown_s
        self.yellow_cooldown_s = yellow_cooldown_s
        self.send_yellow_alerts = send_yellow_alerts

        self.previous_status: Optional[str] = None
        self.last_alert_time_by_status: dict[str, float] = {}

    def evaluate(self, recommendation: Any) -> AlertDecision:
        now_s = time.time()
        current_status = recommendation.status
        previous_status = self.previous_status

        should_send = False
        alert_type = "NO_ALERT"
        reason = "No alert required."
        message = ""

        # 1. Unknown status should be sent because system health may be degraded.
        if current_status == "UNKNOWN":
            should_send = True
            alert_type = "SYSTEM_UNCERTAIN"
            reason = "Risk status is unknown; users should verify local conditions."
            message = self._format_message(recommendation, alert_type)

        # 2. Escalation: any move to a higher risk should alert.
        elif self._is_escalation(previous_status, current_status):
            if current_status in {"ORANGE", "RED"}:
                should_send = True
                alert_type = "ESCALATION"
                reason = f"Risk escalated from {previous_status} to {current_status}."
                message = self._format_message(recommendation, alert_type)

            elif current_status == "YELLOW" and self.send_yellow_alerts:
                should_send = True
                alert_type = "CAUTION"
                reason = "Risk escalated to YELLOW and yellow alerts are enabled."
                message = self._format_message(recommendation, alert_type)

        # 3. Persistent RED/ORANGE: resend after cooldown.
        elif current_status in {"ORANGE", "RED"}:
            cooldown_s = self._cooldown_for_status(current_status)

            if self._cooldown_expired(current_status, now_s, cooldown_s):
                should_send = True
                alert_type = "REMINDER"
                reason = f"{current_status} condition persists and cooldown expired."
                message = self._format_message(recommendation, alert_type)

        # 4. Recovery: dangerous status returned to lower risk.
        if self._is_recovery(previous_status, current_status):
            should_send = True
            alert_type = "RECOVERY"
            reason = f"Risk reduced from {previous_status} to {current_status}."
            message = self._format_message(recommendation, alert_type)

        if should_send:
            self.last_alert_time_by_status[current_status] = now_s

        self.previous_status = current_status

        return AlertDecision(
            node_id=recommendation.node_id,
            should_send=should_send,
            alert_type=alert_type,
            current_status=current_status,
            previous_status=previous_status,
            message=message,
            reason=reason,
            calculated_time_s=now_s,
        )

    def _is_escalation(
        self,
        previous_status: Optional[str],
        current_status: str,
    ) -> bool:
        if previous_status is None:
            return current_status in {"ORANGE", "RED"}

        return RISK_PRIORITY.get(current_status, -1) > RISK_PRIORITY.get(
            previous_status,
            -1,
        )

    def _is_recovery(
        self,
        previous_status: Optional[str],
        current_status: str,
    ) -> bool:
        if previous_status not in {"ORANGE", "RED"}:
            return False

        return current_status in {"GREEN", "YELLOW"}

    def _cooldown_expired(
        self,
        status: str,
        now_s: float,
        cooldown_s: int,
    ) -> bool:
        last_alert_time = self.last_alert_time_by_status.get(status)

        if last_alert_time is None:
            return True

        return (now_s - last_alert_time) >= cooldown_s

    def _cooldown_for_status(self, status: str) -> int:
        if status == "RED":
            return self.red_cooldown_s

        if status == "ORANGE":
            return self.orange_cooldown_s

        if status == "YELLOW":
            return self.yellow_cooldown_s

        return self.orange_cooldown_s

    def _format_message(self, recommendation: Any, alert_type: str) -> str:
        prefix = self._prefix_for_alert_type(alert_type, recommendation.status)

        return (
            f"{prefix}\n\n"
            f"Node: {recommendation.node_id}\n"
            f"Status: {recommendation.status}\n"
            f"Action: {recommendation.action_level}\n\n"
            f"{recommendation.public_message}\n\n"
            f"Technical Summary:\n"
            f"{recommendation.technical_summary}"
        )

    def _prefix_for_alert_type(self, alert_type: str, status: str) -> str:
        if alert_type == "ESCALATION":
            return "[ALERT] RiverGuardian AI Alert"

        if alert_type == "REMINDER":
            return "[REMINDER] RiverGuardian AI Status Reminder"

        if alert_type == "RECOVERY":
            return "[RECOVERY] RiverGuardian AI Recovery Update"

        if alert_type == "SYSTEM_UNCERTAIN":
            return "[NOTICE] RiverGuardian AI System Notice"

        if status == "RED":
            return "[EMERGENCY] RiverGuardian AI Emergency Alert"

        return "[UPDATE] RiverGuardian AI Update"