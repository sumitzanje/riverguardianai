import json
from pathlib import Path

from weather_fetcher import AmbientWeatherFetcher


def main() -> None:
    secrets_path = (
        Path(__file__).resolve().parents[1]
        / "config"
        / "ambient_weather_secrets.json"
    )

    if not secrets_path.exists():
        raise FileNotFoundError(
            "Missing config/ambient_weather_secrets.json. "
            "Create it from config/ambient_weather_secrets.example.json"
        )

    fetcher = AmbientWeatherFetcher(secrets_path)
    weather = fetcher.fetch_latest()

    print(json.dumps(weather.to_dict(), indent=2))


if __name__ == "__main__":
    main()