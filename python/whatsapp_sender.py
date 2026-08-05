"""
RiverGuardian AI
Module 11: WhatsApp Sender

Purpose:
    Deliver alert messages to WhatsApp through a configured provider.

Design:
    - Optional and fail-safe: runtime must not crash if sending fails.
    - Provider-based routing (TWILIO or WEBHOOK).
"""

from __future__ import annotations

import base64
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class WhatsAppSendResult:
    attempted: bool
    sent: bool
    provider: str
    status_code: Optional[int]
    message_id: Optional[str]
    error: Optional[str]
    calculated_time_s: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "attempted": self.attempted,
            "sent": self.sent,
            "provider": self.provider,
            "status_code": self.status_code,
            "message_id": self.message_id,
            "error": self.error,
            "calculated_time_s": self.calculated_time_s,
        }


class WhatsAppSender:
    def __init__(
        self,
        enabled: bool = False,
        provider: str = "TWILIO",
        timeout_s: int = 10,
        twilio_account_sid: Optional[str] = None,
        twilio_auth_token: Optional[str] = None,
        whatsapp_from: Optional[str] = None,
        whatsapp_to: Optional[str] = None,
        webhook_url: Optional[str] = None,
        webhook_bearer_token: Optional[str] = None,
    ) -> None:
        self.enabled = enabled
        self.provider = provider.upper().strip()
        self.timeout_s = timeout_s

        self.twilio_account_sid = twilio_account_sid
        self.twilio_auth_token = twilio_auth_token
        self.whatsapp_from = whatsapp_from
        self.whatsapp_to = whatsapp_to

        self.webhook_url = webhook_url
        self.webhook_bearer_token = webhook_bearer_token

    def send_message(self, *, node_id: str, alert_type: str, message: str) -> WhatsAppSendResult:
        now = time.time()

        if not self.enabled:
            return WhatsAppSendResult(
                attempted=False,
                sent=False,
                provider=self.provider,
                status_code=None,
                message_id=None,
                error="WHATSAPP_DISABLED",
                calculated_time_s=now,
            )

        if self.provider == "TWILIO":
            return self._send_twilio(node_id=node_id, alert_type=alert_type, message=message)

        if self.provider == "WEBHOOK":
            return self._send_webhook(node_id=node_id, alert_type=alert_type, message=message)

        return WhatsAppSendResult(
            attempted=True,
            sent=False,
            provider=self.provider,
            status_code=None,
            message_id=None,
            error=f"UNSUPPORTED_PROVIDER:{self.provider}",
            calculated_time_s=time.time(),
        )

    def _send_twilio(self, *, node_id: str, alert_type: str, message: str) -> WhatsAppSendResult:
        now = time.time()

        if (
            not self.twilio_account_sid
            or not self.twilio_auth_token
            or not self.whatsapp_from
            or not self.whatsapp_to
        ):
            return WhatsAppSendResult(
                attempted=True,
                sent=False,
                provider="TWILIO",
                status_code=None,
                message_id=None,
                error="TWILIO_CONFIG_MISSING",
                calculated_time_s=now,
            )

        url = (
            f"https://api.twilio.com/2010-04-01/Accounts/"
            f"{self.twilio_account_sid}/Messages.json"
        )

        payload = urllib.parse.urlencode(
            {
                "From": self.whatsapp_from,
                "To": self.whatsapp_to,
                "Body": message,
            }
        ).encode("utf-8")

        token_bytes = f"{self.twilio_account_sid}:{self.twilio_auth_token}".encode("utf-8")
        basic_auth = base64.b64encode(token_bytes).decode("utf-8")

        request = urllib.request.Request(url=url, data=payload, method="POST")
        request.add_header("Authorization", f"Basic {basic_auth}")
        request.add_header("Content-Type", "application/x-www-form-urlencoded")

        try:
            with urllib.request.urlopen(request, timeout=self.timeout_s) as response:
                body = response.read().decode("utf-8", errors="replace")
                parsed = json.loads(body) if body else {}
                status_code = int(response.status)
                sent = 200 <= status_code < 300

                return WhatsAppSendResult(
                    attempted=True,
                    sent=sent,
                    provider="TWILIO",
                    status_code=status_code,
                    message_id=str(parsed.get("sid")) if parsed.get("sid") else None,
                    error=None if sent else body,
                    calculated_time_s=time.time(),
                )

        except urllib.error.HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            return WhatsAppSendResult(
                attempted=True,
                sent=False,
                provider="TWILIO",
                status_code=int(exc.code),
                message_id=None,
                error=error_body or str(exc),
                calculated_time_s=time.time(),
            )
        except Exception as exc:
            return WhatsAppSendResult(
                attempted=True,
                sent=False,
                provider="TWILIO",
                status_code=None,
                message_id=None,
                error=str(exc),
                calculated_time_s=time.time(),
            )

    def _send_webhook(self, *, node_id: str, alert_type: str, message: str) -> WhatsAppSendResult:
        now = time.time()

        if not self.webhook_url:
            return WhatsAppSendResult(
                attempted=True,
                sent=False,
                provider="WEBHOOK",
                status_code=None,
                message_id=None,
                error="WEBHOOK_URL_MISSING",
                calculated_time_s=now,
            )

        payload = {
            "channel": "whatsapp",
            "node_id": node_id,
            "alert_type": alert_type,
            "message": message,
            "sent_time_s": now,
        }

        data = json.dumps(payload).encode("utf-8")

        request = urllib.request.Request(url=self.webhook_url, data=data, method="POST")
        request.add_header("Content-Type", "application/json")

        if self.webhook_bearer_token:
            request.add_header("Authorization", f"Bearer {self.webhook_bearer_token}")

        try:
            with urllib.request.urlopen(request, timeout=self.timeout_s) as response:
                status_code = int(response.status)
                sent = 200 <= status_code < 300

                return WhatsAppSendResult(
                    attempted=True,
                    sent=sent,
                    provider="WEBHOOK",
                    status_code=status_code,
                    message_id=None,
                    error=None if sent else "WEBHOOK_NON_2XX",
                    calculated_time_s=time.time(),
                )
        except urllib.error.HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            return WhatsAppSendResult(
                attempted=True,
                sent=False,
                provider="WEBHOOK",
                status_code=int(exc.code),
                message_id=None,
                error=error_body or str(exc),
                calculated_time_s=time.time(),
            )
        except Exception as exc:
            return WhatsAppSendResult(
                attempted=True,
                sent=False,
                provider="WEBHOOK",
                status_code=None,
                message_id=None,
                error=str(exc),
                calculated_time_s=time.time(),
            )
