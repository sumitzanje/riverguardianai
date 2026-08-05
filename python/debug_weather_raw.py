import json
from pathlib import Path

import requests


def main() -> None:
    secrets_path = (
        Path(__file__).resolve().parents[1]
        / "config"
        / "ambient_weather_secrets.json"
    )

    with open(secrets_path, "r", encoding="utf-8") as file:
        secrets = json.load(file)

    url = f"https://api.ambientweather.net/v1/devices/{secrets['mac_address']}"

    params = {
        "apiKey": secrets["api_key"],
        "applicationKey": secrets["application_key"],
        "limit": 1,
    }

    response = requests.get(url, params=params, timeout=10)
    print("STATUS:", response.status_code)
    print(json.dumps(response.json(), indent=2))


if __name__ == "__main__":
    main()