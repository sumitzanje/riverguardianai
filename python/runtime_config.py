from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def _to_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _to_int_or_none(value: str) -> int | None:
    text = value.strip().lower()
    if text in {"", "none", "null"}:
        return None
    return int(value)


def _load_dotenv(dotenv_path: Path) -> dict[str, str]:
    env_map: dict[str, str] = {}

    if not dotenv_path.exists():
        return env_map

    for raw_line in dotenv_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            env_map[key] = value

    return env_map


def load_runtime_settings(project_root: Path) -> dict[str, Any]:
    settings_path = project_root / "config" / "settings.json"

    with open(settings_path, "r", encoding="utf-8") as file:
        settings: dict[str, Any] = json.load(file)

    dotenv_override = os.getenv("RIVERGUARDIAN_ENV_FILE")
    dotenv_path = Path(dotenv_override) if dotenv_override else (project_root / ".env")

    dotenv_values = _load_dotenv(dotenv_path)

    # OS environment takes precedence over .env values.
    for key, value in dotenv_values.items():
        os.environ.setdefault(key, value)

    env = os.environ

    if "MOCK_MODE" in env:
        settings["mock_mode"] = _to_bool(env["MOCK_MODE"])
    if "SERIAL_PORT" in env:
        settings["serial_port"] = env["SERIAL_PORT"]
    if "BAUD_RATE" in env:
        settings["baud_rate"] = int(env["BAUD_RATE"])
    if "MONITORING_INTERVAL_SECONDS" in env:
        settings["monitoring_interval_seconds"] = float(env["MONITORING_INTERVAL_SECONDS"])
    if "MAX_RUNTIME_CYCLES" in env:
        settings["max_runtime_cycles"] = _to_int_or_none(env["MAX_RUNTIME_CYCLES"])

    if "DANGER_DISTANCE_CM" in env:
        settings["danger_distance_cm"] = float(env["DANGER_DISTANCE_CM"])
    if "CRITICAL_CLEARANCE_CM" in env:
        settings["critical_clearance_cm"] = float(env["CRITICAL_CLEARANCE_CM"])
    if "MINIMUM_RISE_RATE_CM_MIN" in env:
        settings["minimum_rise_rate_cm_min"] = float(env["MINIMUM_RISE_RATE_CM_MIN"])
    if "ORANGE_TIME_TO_UNSAFE_MIN" in env:
        settings["orange_time_to_unsafe_min"] = float(env["ORANGE_TIME_TO_UNSAFE_MIN"])
    if "YELLOW_TIME_TO_UNSAFE_MIN" in env:
        settings["yellow_time_to_unsafe_min"] = float(env["YELLOW_TIME_TO_UNSAFE_MIN"])

    if "SEND_YELLOW_ALERTS" in env:
        settings["send_yellow_alerts"] = _to_bool(env["SEND_YELLOW_ALERTS"])
    if "ORANGE_COOLDOWN_S" in env:
        settings["orange_cooldown_s"] = int(env["ORANGE_COOLDOWN_S"])
    if "RED_COOLDOWN_S" in env:
        settings["red_cooldown_s"] = int(env["RED_COOLDOWN_S"])
    if "YELLOW_COOLDOWN_S" in env:
        settings["yellow_cooldown_s"] = int(env["YELLOW_COOLDOWN_S"])

    if "UPLOAD_MODE" in env:
        settings["upload_mode"] = env["UPLOAD_MODE"]

    if "UPLOAD_ENDPOINT" in env:
        settings["upload_endpoint"] = env["UPLOAD_ENDPOINT"]
    elif "SUPABASE_URL" in env:
        settings["upload_endpoint"] = env["SUPABASE_URL"]

    if "UPLOAD_API_KEY" in env:
        settings["upload_api_key"] = env["UPLOAD_API_KEY"]
    elif "SUPABASE_KEY" in env:
        settings["upload_api_key"] = env["SUPABASE_KEY"]

    if "UPLOAD_TABLE_NAME" in env:
        settings["upload_table_name"] = env["UPLOAD_TABLE_NAME"]

    if "LOG_LEVEL" in env:
        settings["log_level"] = env["LOG_LEVEL"]

    if "DEVICE_ID" in env:
        settings["device_id"] = env["DEVICE_ID"]
    if "SITE_ID" in env:
        settings["site_id"] = env["SITE_ID"]

    if "WHATSAPP_ENABLED" in env:
        settings["whatsapp_enabled"] = _to_bool(env["WHATSAPP_ENABLED"])
    if "WHATSAPP_PROVIDER" in env:
        settings["whatsapp_provider"] = env["WHATSAPP_PROVIDER"]
    if "WHATSAPP_TIMEOUT_S" in env:
        settings["whatsapp_timeout_s"] = int(env["WHATSAPP_TIMEOUT_S"])

    if "TWILIO_ACCOUNT_SID" in env:
        settings["twilio_account_sid"] = env["TWILIO_ACCOUNT_SID"]
    if "TWILIO_AUTH_TOKEN" in env:
        settings["twilio_auth_token"] = env["TWILIO_AUTH_TOKEN"]
    if "WHATSAPP_FROM" in env:
        settings["whatsapp_from"] = env["WHATSAPP_FROM"]
    if "WHATSAPP_TO" in env:
        settings["whatsapp_to"] = env["WHATSAPP_TO"]

    if "WHATSAPP_WEBHOOK_URL" in env:
        settings["whatsapp_webhook_url"] = env["WHATSAPP_WEBHOOK_URL"]
    if "WHATSAPP_WEBHOOK_BEARER_TOKEN" in env:
        settings["whatsapp_webhook_bearer_token"] = env["WHATSAPP_WEBHOOK_BEARER_TOKEN"]

    if "SUPABASE_SERVICE_ROLE_KEY" in env:
        settings["supabase_service_role_key"] = env["SUPABASE_SERVICE_ROLE_KEY"]

    if "TELEGRAM_ENABLED" in env:
        settings["telegram_enabled"] = _to_bool(env["TELEGRAM_ENABLED"])
    if "TELEGRAM_BOT_TOKEN" in env:
        settings["telegram_bot_token"] = env["TELEGRAM_BOT_TOKEN"]
    if "TELEGRAM_CHAT_ID" in env:
        settings["telegram_chat_id"] = env["TELEGRAM_CHAT_ID"]
    if "TELEGRAM_TIMEOUT_S" in env:
        settings["telegram_timeout_s"] = int(env["TELEGRAM_TIMEOUT_S"])

    if "ALERT_NOTIFIER_POLL_SECONDS" in env:
        settings["alert_notifier_poll_seconds"] = int(env["ALERT_NOTIFIER_POLL_SECONDS"])
    if "ALERT_NOTIFIER_BATCH_SIZE" in env:
        settings["alert_notifier_batch_size"] = int(env["ALERT_NOTIFIER_BATCH_SIZE"])
    if "ALERT_NOTIFIER_TIMEOUT_S" in env:
        settings["alert_notifier_timeout_s"] = int(env["ALERT_NOTIFIER_TIMEOUT_S"])
    if "WHATSAPP_FALLBACK_ENABLED" in env:
        settings["whatsapp_fallback_enabled"] = _to_bool(env["WHATSAPP_FALLBACK_ENABLED"])

    if "MODEM_AT_PORT" in env:
        settings["modem_at_port"] = env["MODEM_AT_PORT"]
    if "MODEM_INTERFACE" in env:
        settings["modem_interface"] = env["MODEM_INTERFACE"]
    if "MODEM_APN" in env:
        settings["modem_apn"] = env["MODEM_APN"]
    if "MODEM_BAUD" in env:
        settings["modem_baud"] = int(env["MODEM_BAUD"])
    if "MODEM_RECOVERY_ENABLED" in env:
        settings["modem_recovery_enabled"] = _to_bool(env["MODEM_RECOVERY_ENABLED"])
    if "MODEM_RECOVERY_MIN_INTERVAL_S" in env:
        settings["modem_recovery_min_interval_s"] = int(env["MODEM_RECOVERY_MIN_INTERVAL_S"])
    if "MODEM_RECOVERY_MAX_INTERVAL_S" in env:
        settings["modem_recovery_max_interval_s"] = int(env["MODEM_RECOVERY_MAX_INTERVAL_S"])
    if "MODEM_DHCP_TIMEOUT_S" in env:
        settings["modem_dhcp_timeout_s"] = int(env["MODEM_DHCP_TIMEOUT_S"])

    return settings
