"""
RiverGuardian AI
Supabase Alert Notifier

Purpose:
    Read alert events from Supabase and deliver notifications.

Delivery policy:
    1) Telegram is primary (free-friendly channel)
    2) WhatsApp is optional fallback when enabled

Safety:
    - Non-blocking and retry-friendly.
    - Keeps checkpoint state so each event is sent once after success.
"""

from __future__ import annotations

import argparse
import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from runtime_config import load_runtime_settings
from whatsapp_sender import WhatsAppSender


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


class SupabaseAlertNotifier:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.settings = load_runtime_settings(root)

        self.supabase_url = str(self.settings.get("upload_endpoint") or "").strip()
        self.supabase_table = str(
            self.settings.get("upload_table_name", "riverguardian_events")
        ).strip()
        self.supabase_key = str(
            self.settings.get("supabase_service_role_key")
            or self.settings.get("upload_api_key")
            or ""
        ).strip()

        self.poll_seconds = int(self.settings.get("alert_notifier_poll_seconds", 12))
        self.batch_size = int(self.settings.get("alert_notifier_batch_size", 25))
        self.timeout_s = int(self.settings.get("alert_notifier_timeout_s", 10))

        self.telegram_enabled = bool(self.settings.get("telegram_enabled", False))
        self.telegram_bot_token = str(self.settings.get("telegram_bot_token") or "").strip()
        self.telegram_chat_id = str(self.settings.get("telegram_chat_id") or "").strip()
        self.telegram_timeout_s = int(self.settings.get("telegram_timeout_s", 10))

        self.whatsapp_fallback_enabled = bool(
            self.settings.get("whatsapp_fallback_enabled", False)
        )

        self.whatsapp_sender = WhatsAppSender(
            enabled=self.whatsapp_fallback_enabled,
            provider=str(self.settings.get("whatsapp_provider", "TWILIO")),
            timeout_s=int(self.settings.get("whatsapp_timeout_s", 10)),
            twilio_account_sid=self.settings.get("twilio_account_sid"),
            twilio_auth_token=self.settings.get("twilio_auth_token"),
            whatsapp_from=self.settings.get("whatsapp_from"),
            whatsapp_to=self.settings.get("whatsapp_to"),
            webhook_url=self.settings.get("whatsapp_webhook_url"),
            webhook_bearer_token=self.settings.get("whatsapp_webhook_bearer_token"),
        )

        self.state_path = self.root / "data" / "alert_notifier_state.json"
        self.state_path.parent.mkdir(parents=True, exist_ok=True)

    def run_forever(self) -> None:
        logging.info("Supabase Alert Notifier started.")
        logging.info("Supabase table: %s", self.supabase_table)
        logging.info("Telegram enabled: %s", self.telegram_enabled)
        logging.info(
            "WhatsApp fallback enabled: %s",
            self.whatsapp_fallback_enabled and self.whatsapp_sender.enabled,
        )

        while True:
            try:
                processed = self.run_once()
                if processed == 0:
                    time.sleep(self.poll_seconds)
            except Exception as exc:
                logging.exception("Notifier cycle failed: %s", exc)
                time.sleep(self.poll_seconds)

    def run_once(self) -> int:
        self._validate_config()

        state = self._load_state()
        last_id = int(state.get("last_successful_event_id", 0))

        events = self._fetch_alert_events(last_id=last_id, limit=self.batch_size)

        if not events:
            return 0

        processed = 0
        for event in events:
            event_id = int(event["id"])

            delivered = self._deliver_event(event)
            if delivered:
                state["last_successful_event_id"] = event_id
                self._save_state(state)
                processed += 1
            else:
                logging.warning(
                    "Delivery failed for event id=%s. Will retry next cycle.", event_id
                )
                break

        return processed

    def _validate_config(self) -> None:
        if not self.supabase_url:
            raise RuntimeError("Missing Supabase URL in config (SUPABASE_URL).")
        if not self.supabase_key:
            raise RuntimeError(
                "Missing Supabase key for notifier. Set SUPABASE_SERVICE_ROLE_KEY "
                "(recommended) or SUPABASE_KEY with read access."
            )
        if not self.telegram_enabled:
            raise RuntimeError("Telegram is disabled. Set TELEGRAM_ENABLED=true.")
        if not self.telegram_bot_token or not self.telegram_chat_id:
            raise RuntimeError(
                "Telegram config missing. Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID."
            )

    def _fetch_alert_events(self, *, last_id: int, limit: int) -> list[dict[str, Any]]:
        query = urllib.parse.urlencode(
            {
                "select": "id,created_at,node_id,device_id,site_id,fused_risk,recommendation_status,alert_type,alert_message,send_whatsapp,alert_should_send",
                "alert_should_send": "eq.true",
                "id": f"gt.{last_id}",
                "order": "id.asc",
                "limit": str(limit),
            }
        )

        url = f"{self.supabase_url.rstrip('/')}/rest/v1/{self.supabase_table}?{query}"
        request = urllib.request.Request(url=url, method="GET")
        request.add_header("apikey", self.supabase_key)
        request.add_header("Authorization", f"Bearer {self.supabase_key}")
        request.add_header("Accept", "application/json")

        try:
            with urllib.request.urlopen(request, timeout=self.timeout_s) as response:
                body = response.read().decode("utf-8", errors="replace")
                rows = json.loads(body) if body else []
                if not isinstance(rows, list):
                    return []
                return [row for row in rows if isinstance(row, dict)]
        except urllib.error.HTTPError as exc:
            details = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Supabase fetch failed ({exc.code}): {details}") from exc

    def _deliver_event(self, event: dict[str, Any]) -> bool:
        text = self._build_telegram_message(event)

        telegram_ok = self._send_telegram_message(text)
        if telegram_ok:
            logging.info("Telegram sent for event id=%s", event.get("id"))
            return True

        can_try_whatsapp = (
            self.whatsapp_fallback_enabled
            and self.whatsapp_sender.enabled
            and bool(event.get("send_whatsapp", False))
        )

        if not can_try_whatsapp:
            return False

        wa = self.whatsapp_sender.send_message(
            node_id=str(event.get("node_id") or "UNKNOWN"),
            alert_type=str(event.get("alert_type") or "ALERT"),
            message=str(event.get("alert_message") or text),
        )

        if wa.sent:
            logging.info(
                "WhatsApp fallback sent for event id=%s via %s",
                event.get("id"),
                wa.provider,
            )
            return True

        logging.warning(
            "WhatsApp fallback failed for event id=%s: %s",
            event.get("id"),
            wa.error,
        )
        return False

    def _send_telegram_message(self, message: str) -> bool:
        url = f"https://api.telegram.org/bot{self.telegram_bot_token}/sendMessage"

        payload = {
            "chat_id": self.telegram_chat_id,
            "text": message,
            "disable_web_page_preview": True,
        }

        data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(url=url, data=data, method="POST")
        request.add_header("Content-Type", "application/json")

        try:
            with urllib.request.urlopen(request, timeout=self.telegram_timeout_s) as response:
                return 200 <= int(response.status) < 300
        except Exception as exc:
            logging.warning("Telegram send failed: %s", exc)
            return False

    @staticmethod
    def _build_telegram_message(event: dict[str, Any]) -> str:
        return (
            "RiverGuardian AI Alert\n\n"
            f"Event ID: {event.get('id')}\n"
            f"Node: {event.get('node_id')}\n"
            f"Device: {event.get('device_id')}\n"
            f"Site: {event.get('site_id')}\n"
            f"Risk: {event.get('fused_risk')}\n"
            f"Status: {event.get('recommendation_status')}\n"
            f"Alert Type: {event.get('alert_type')}\n\n"
            f"{event.get('alert_message') or 'No alert message provided.'}"
        )

    def _load_state(self) -> dict[str, Any]:
        if not self.state_path.exists():
            return {"last_successful_event_id": 0}

        try:
            state = json.loads(self.state_path.read_text(encoding="utf-8"))
            if not isinstance(state, dict):
                return {"last_successful_event_id": 0}
            return state
        except Exception:
            return {"last_successful_event_id": 0}

    def _save_state(self, state: dict[str, Any]) -> None:
        self.state_path.write_text(
            json.dumps(state, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="RiverGuardian Supabase alert notifier")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Process available events once and exit.",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )

    notifier = SupabaseAlertNotifier(project_root())

    if args.once:
        processed = notifier.run_once()
        logging.info("Notifier one-shot complete. processed=%s", processed)
        return

    notifier.run_forever()


if __name__ == "__main__":
    main()
