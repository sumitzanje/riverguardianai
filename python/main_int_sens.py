import json
import time
from pathlib import Path

from bridge_interface import BridgeInterface


def load_settings() -> dict:
    base_dir = Path(__file__).resolve().parent
    settings_path = base_dir.parent / "config" / "settings.json"

    if not settings_path.exists():
        raise FileNotFoundError(f"Settings file not found: {settings_path}")

    print(f"Using settings file: {settings_path}")

    with open(settings_path, "r", encoding="utf-8") as f:
        return json.load(f)


def main() -> None:
    settings = load_settings()

    mock_mode = settings.get("mock_mode", True)
    serial_port = settings.get("serial_port", None)
    baud_rate = settings.get("baud_rate", 115200)
    monitoring_interval_seconds = settings.get("monitoring_interval_seconds", 5)
    max_runtime_cycles = settings.get("max_runtime_cycles", None)

    bridge = None

    try:
        if mock_mode:
            print("Running in MOCK mode...")
            bridge = BridgeInterface(mock_mode=True)
        else:
            if not serial_port:
                raise ValueError(
                    "serial_port is required in config/settings.json when mock_mode is false."
                )

            print(f"Running in SENSOR mode on {serial_port} at {baud_rate} baud...")
            bridge = BridgeInterface(
                serial_port=serial_port,
                baud_rate=baud_rate,
                mock_mode=False,
            )

        if max_runtime_cycles is None:
            print("Continuous mode enabled. Press Ctrl + C to stop.")
        else:
            print(f"Limited test mode enabled. Max cycles: {max_runtime_cycles}")

        cycle = 0
        while True:
            packet = bridge.read_packet()
            print(packet.to_dict())

            cycle += 1
            if max_runtime_cycles is not None and cycle >= max_runtime_cycles:
                print("Reached max_runtime_cycles. Stopping.")
                break

            time.sleep(monitoring_interval_seconds)

    except KeyboardInterrupt:
        print("\nStopped by user.")

    except Exception as exc:
        print(f"Runtime error: {exc}")

    finally:
        if bridge is not None and hasattr(bridge, "_serial_connection"):
            serial_conn = bridge._serial_connection
            if serial_conn is not None:
                try:
                    serial_conn.close()
                except Exception:
                    pass


if __name__ == "__main__":
    main()