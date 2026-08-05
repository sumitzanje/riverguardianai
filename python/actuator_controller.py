class ActuatorController:
    def __init__(self, config: dict):
        self.enabled = bool(config.get("alerts", {}).get("enable_actuator", False))

    def update(self, risk: str):
        # TODO: Send command back to MCU bridge/RPMSG/serial.
        # For now, print the intended command.
        if not self.enabled:
            return
        if risk in ("ORANGE", "RED"):
            print(f"[ACTUATOR] Activate local warning for {risk}")
        else:
            print("[ACTUATOR] Warning off")
