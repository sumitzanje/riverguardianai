type EventRecord = {
  id: number;
  created_at: string;
  node_id: string;
  site_id: string | null;
  fused_risk: string | null;
  recommendation_status: string | null;
  distance_cm: number | null;
  raw_distance_cm: number | null;
  accepted_distance_cm: number | null;
  candidate_distance_cm: number | null;
  sensor_status: string | null;
  measurement_state: string | null;
  sensor_error: string | null;
  packet_sequence: number | null;
  fw_profile: string | null;
  fw_build: string | null;
  clearance_cm: number | null;
  rise_rate_cm_min: number | null;
  time_to_unsafe_min: number | null;
  alert_type: string | null;
  alert_message: string | null;
};

function ageMinutes(isoTime: string): number {
  const t = new Date(isoTime).getTime();
  return Math.max(0, Math.round((Date.now() - t) / 60000));
}

function fmtNum(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "N/A";
  }
  return Number(value).toFixed(digits);
}

export function formatStatusMessage(latest: EventRecord | null, staleAfterMin: number): string {
  if (!latest) {
    return "RiverGuardian AI\n\nNo sensor data found yet in Supabase.";
  }

  const risk = latest.recommendation_status ?? latest.fused_risk ?? "UNKNOWN";
  const ageMin = ageMinutes(latest.created_at);
  const stale = ageMin >= staleAfterMin;

  return [
    `Current River Status: ${risk}`,
    `Site: ${latest.site_id ?? "N/A"}`,
    `Node: ${latest.node_id}`,
    `Water clearance: ${fmtNum(latest.clearance_cm, 1)} cm`,
    `Rise rate: ${fmtNum(latest.rise_rate_cm_min, 2)} cm/min`,
    `Time to unsafe: ${latest.time_to_unsafe_min == null ? "N/A" : `${Math.round(latest.time_to_unsafe_min)} min`}`,
    `Sensor status: ${latest.sensor_status ?? "N/A"}`,
    `Measurement state: ${latest.measurement_state ?? "N/A"}`,
    `Sensor error: ${latest.sensor_error ?? "None"}`,
    `Last reading age: ${ageMin} min`,
    stale
      ? "Stale-data warning: Latest reading may not represent current river conditions."
      : "Data freshness: current.",
  ].join("\n");
}

export function formatTrendMessage(rows: EventRecord[]): string {
  if (rows.length < 2) {
    return "Recent Trend\n\nNot enough data for trend calculation yet.";
  }

  const oldest = rows[rows.length - 1];
  const newest = rows[0];

  const riseDelta =
    oldest.clearance_cm != null && newest.clearance_cm != null
      ? oldest.clearance_cm - newest.clearance_cm
      : null;

  const highestRiseRate = rows.reduce((acc, r) => {
    if (r.rise_rate_cm_min == null) return acc;
    return Math.max(acc, r.rise_rate_cm_min);
  }, 0);

  return [
    "Recent Trend (last 6h)",
    `Clearance change: ${riseDelta == null ? "N/A" : `${fmtNum(riseDelta, 1)} cm`}`,
    `Current rise rate: ${fmtNum(newest.rise_rate_cm_min, 2)} cm/min`,
    `Highest rise rate: ${fmtNum(highestRiseRate, 2)} cm/min`,
    `Current risk: ${newest.recommendation_status ?? newest.fused_risk ?? "UNKNOWN"}`,
  ].join("\n");
}

export function formatAlertsMessage(rows: EventRecord[]): string {
  if (rows.length === 0) {
    return "Active Alerts\n\nNo recent alert events found.";
  }

  const lines = ["Recent Alert Events:"];
  for (const row of rows.slice(0, 5)) {
    lines.push(
      `- [${row.alert_type ?? "ALERT"}] ${row.recommendation_status ?? row.fused_risk ?? "UNKNOWN"} | ${row.alert_message ?? "No message"}`,
    );
  }

  return lines.join("\n");
}

export function formatHealthMessage(latest: EventRecord | null, staleAfterMin: number): string {
  if (!latest) {
    return "Device Health\n\nNo data received yet.";
  }

  const ageMin = ageMinutes(latest.created_at);
  const online = ageMin < staleAfterMin;

  return [
    "RiverGuardian Device Health",
    `Device: ${online ? "Online" : "Offline or stale"}`,
    `Sensor: ${latest.sensor_status ?? "N/A"}`,
    `Measurement state: ${latest.measurement_state ?? "N/A"}`,
    `Candidate distance: ${fmtNum(latest.candidate_distance_cm, 1)} cm`,
    `Accepted distance: ${fmtNum(latest.accepted_distance_cm, 1)} cm`,
    `Packet sequence: ${latest.packet_sequence ?? "N/A"}`,
    "LTE: N/A (link metrics not yet in cloud payload)",
    `Last successful upload: ${ageMin} min ago`,
    "Local pending records: N/A (not yet uploaded)",
    "Application uptime: N/A (not yet uploaded)",
    `Software version: ${latest.fw_build ?? latest.fw_profile ?? "N/A"}`,
  ].join("\n");
}
