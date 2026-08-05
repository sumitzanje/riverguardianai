from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen
from typing import Any, Optional


@dataclass
class WeatherPacket:
    station_status: str
    station_name: Optional[str]
    rain_hourly_mm: Optional[float]
    rain_daily_mm: Optional[float]
    rain_weekly_mm: Optional[float]
    rain_monthly_mm: Optional[float]
    temp_c: Optional[float]
    humidity_percent: Optional[float]
    pressure_hpa: Optional[float]
    windspeed_kmh: Optional[float]
    source_time_utc_ms: Optional[int]
    error: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__


class AmbientWeatherFetcher:
    BASE_URL = "https://api.ambientweather.net/v1"

    def __init__(self, secrets_path: Path) -> None:
        with open(secrets_path, "r", encoding="utf-8") as file:
            secrets = json.load(file)

        self.api_key = secrets["api_key"]
        self.application_key = secrets["application_key"]
        self.mac_address = secrets["mac_address"]

    def fetch_latest(self) -> WeatherPacket:
        url = f"{self.BASE_URL}/devices/{self.mac_address}"

        params = {
            "apiKey": self.api_key,
            "applicationKey": self.application_key,
            "limit": 1,
        }
        request_url = f"{url}?{urlencode(params)}"

        try:
            with urlopen(request_url, timeout=10) as response:
                status_code = response.getcode()
                if status_code is not None and status_code >= 400:
                    return self._fault(f"HTTP {status_code}")

                payload = response.read().decode("utf-8")
                data = json.loads(payload)

            if not isinstance(data, list) or len(data) == 0:
                return self._fault("NO_WEATHER_DATA_RETURNED")

            first = data[0]

            if "lastData" in first:
                latest = first.get("lastData", {})
                station_name = first.get("info", {}).get("name")
            else:
                latest = first
                station_name = first.get("name")

            return self._parse(latest, station_name)

        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
            return self._fault(str(exc))
        except Exception as exc:
            return self._fault(str(exc))

    def _parse(self, latest: dict[str, Any], station_name: Optional[str]) -> WeatherPacket:
        return WeatherPacket(
            station_status="OK",
            station_name=station_name,
            rain_hourly_mm=self._inch_to_mm(latest.get("hourlyrainin")),
            rain_daily_mm=self._inch_to_mm(latest.get("dailyrainin")),
            rain_weekly_mm=self._inch_to_mm(latest.get("weeklyrainin")),
            rain_monthly_mm=self._inch_to_mm(latest.get("monthlyrainin")),
            temp_c=self._fahrenheit_to_celsius(latest.get("tempf")),
            humidity_percent=self._to_float(latest.get("humidity")),
            pressure_hpa=self._inhg_to_hpa(latest.get("baromrelin")),
            windspeed_kmh=self._mph_to_kmh(latest.get("windspeedmph")),
            source_time_utc_ms=self._to_int(latest.get("dateutc")),
            error=None,
        )

    def _fault(self, error: str) -> WeatherPacket:
        return WeatherPacket(
            station_status="FAULT",
            station_name=None,
            rain_hourly_mm=None,
            rain_daily_mm=None,
            rain_weekly_mm=None,
            rain_monthly_mm=None,
            temp_c=None,
            humidity_percent=None,
            pressure_hpa=None,
            windspeed_kmh=None,
            source_time_utc_ms=None,
            error=error,
        )

    @staticmethod
    def _to_float(value: Any) -> Optional[float]:
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _to_int(value: Any) -> Optional[int]:
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _inch_to_mm(self, value: Any) -> Optional[float]:
        v = self._to_float(value)
        return None if v is None else round(v * 25.4, 3)

    def _fahrenheit_to_celsius(self, value: Any) -> Optional[float]:
        v = self._to_float(value)
        return None if v is None else round((v - 32) * 5 / 9, 2)

    def _inhg_to_hpa(self, value: Any) -> Optional[float]:
        v = self._to_float(value)
        return None if v is None else round(v * 33.8639, 2)

    def _mph_to_kmh(self, value: Any) -> Optional[float]:
        v = self._to_float(value)
        return None if v is None else round(v * 1.60934, 2)