"use client";

import {
  Activity,
  ArrowDownRight,
  ArrowUpRight,
  CheckCircle2,
  Cloud,
  Cpu,
  Gauge,
  Radio,
  RefreshCw,
  ShieldAlert,
  Signal,
  Waves,
  WifiOff,
} from "lucide-react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { useCallback, useEffect, useMemo, useState } from "react";
import type {
  DashboardResponse,
  RiverGuardianEvent,
} from "@/lib/riverguardian";

type Freshness = "LIVE" | "DELAYED" | "OFFLINE";
type DisplayState =
  | "SAFE"
  | "WARNING"
  | "DANGER"
  | "UNKNOWN"
  | "OFFLINE";

const POLL_MS = 5000;
const LIVE_SECONDS = 75;
const OFFLINE_SECONDS = 180;

function finite(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

function ageSeconds(timestamp?: string | null) {
  if (!timestamp) return Number.POSITIVE_INFINITY;
  return Math.max(0, (Date.now() - new Date(timestamp).getTime()) / 1000);
}

function formatAge(seconds: number) {
  if (!Number.isFinite(seconds)) return "never";
  if (seconds < 5) return "just now";
  if (seconds < 60) return `${Math.floor(seconds)} sec ago`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)} min ago`;
  return `${Math.floor(seconds / 3600)} hr ago`;
}

function formatNumber(value: number | null | undefined, digits = 1) {
  return finite(value) ? value.toFixed(digits) : "—";
}

function determineFreshness(latest?: RiverGuardianEvent): Freshness {
  if (!latest) return "OFFLINE";

  const age = ageSeconds(latest.created_at);

  if (age <= LIVE_SECONDS) return "LIVE";
  if (age <= OFFLINE_SECONDS) return "DELAYED";
  return "OFFLINE";
}

function determineState(
  latest: RiverGuardianEvent | undefined,
  freshness: Freshness
): DisplayState {
  if (!latest || freshness === "OFFLINE") return "OFFLINE";

  if (
    latest.sensor_status !== "OK" ||
    latest.measurement_state !== "OK" ||
    !finite(latest.clearance_cm)
  ) {
    return "UNKNOWN";
  }

  const risk = (
    latest.recommendation_status ||
    latest.fused_risk ||
    ""
  ).toUpperCase();

  if (risk === "RED" || risk === "DANGER" || risk === "CRITICAL") {
    return "DANGER";
  }

  if (risk === "ORANGE" || risk === "YELLOW" || risk === "WARNING") {
    return "WARNING";
  }

  if (risk === "GREEN" || risk === "SAFE") {
    return "SAFE";
  }

  return "UNKNOWN";
}

const stateMeta = {
  SAFE: {
    label: "SAFE",
    className: "state-safe",
    description: "Bridge access condition is currently within safe limits.",
  },
  WARNING: {
    label: "WARNING",
    className: "state-warning",
    description: "Conditions require increased monitoring and attention.",
  },
  DANGER: {
    label: "DANGER",
    className: "state-danger",
    description: "Potentially unsafe bridge-access condition detected.",
  },
  UNKNOWN: {
    label: "UNKNOWN",
    className: "state-unknown",
    description: "Current safety condition cannot be reliably determined.",
  },
  OFFLINE: {
    label: "OFFLINE",
    className: "state-offline",
    description: "Recent telemetry is unavailable. Do not rely on last known state.",
  },
};

function MetricCard({
  icon,
  label,
  value,
  subtext,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  subtext: string;
}) {
  return (
    <div className="metric-card">
      <div className="metric-heading">
        <span className="metric-icon">{icon}</span>
        <span>{label}</span>
      </div>
      <div className="metric-value">{value}</div>
      <div className="metric-subtext">{subtext}</div>
    </div>
  );
}

export default function Dashboard() {
  const [records, setRecords] = useState<RiverGuardianEvent[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [clock, setClock] = useState(() => Date.now());

  const loadData = useCallback(async (manual = false) => {
    try {
      if (manual) setRefreshing(true);

      const response = await fetch("/api/riverguardian", {
        cache: "no-store",
      });

      const payload = await response.json();

      if (!response.ok) {
        throw new Error(payload.error || "Dashboard request failed.");
      }

      const data = payload as DashboardResponse;
      setRecords(Array.isArray(data.records) ? data.records : []);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    const initialLoad = window.setTimeout(() => void loadData(), 0);

    const poll = window.setInterval(() => void loadData(), POLL_MS);
    const ticker = window.setInterval(() => setClock(Date.now()), 1000);

    return () => {
      window.clearTimeout(initialLoad);
      window.clearInterval(poll);
      window.clearInterval(ticker);
    };
  }, [loadData]);

  const latest = records[0];
  const freshness = determineFreshness(latest);
  const displayState = determineState(latest, freshness);
  const status = stateMeta[displayState];

  const latestAge = latest
    ? Math.max(0, (clock - new Date(latest.created_at).getTime()) / 1000)
    : Number.POSITIVE_INFINITY;

  const lastValid = records.find(
    (record) =>
      record.sensor_status === "OK" &&
      record.measurement_state === "OK" &&
      finite(record.clearance_cm)
  );

  const chartData = useMemo(() => {
    const cutoff = clock - 24 * 60 * 60 * 1000;

    return records
      .filter(
        (record) =>
          new Date(record.created_at).getTime() >= cutoff &&
          record.sensor_status === "OK" &&
          record.measurement_state === "OK" &&
          finite(record.clearance_cm)
      )
      .slice()
      .reverse()
      .map((record) => ({
        time: new Date(record.created_at).toLocaleTimeString([], {
          hour: "2-digit",
          minute: "2-digit",
        }),
        clearance: record.clearance_cm,
        risk: record.fused_risk,
      }));
  }, [records, clock]);

  const recentEvents = records.slice(0, 8);

  const currentAlert =
    displayState !== "SAFE"
      ? latest
      : latest?.alert_should_send
        ? latest
        : undefined;

  const riseRate = latest?.rise_rate_cm_min;
  const isRising = finite(riseRate) && riseRate < -0.05;
  const isFalling = finite(riseRate) && riseRate > 0.05;

  return (
    <main className="dashboard-shell">
      <header className="topbar">
        <div className="brand">
          <div className="brand-mark">
            <Waves size={26} />
          </div>
          <div>
            <h1>RiverGuardian AI</h1>
            <p>Bridge Flood &amp; Access Monitoring</p>
          </div>
        </div>

        <div className="topbar-right">
          <div className={`freshness freshness-${freshness.toLowerCase()}`}>
            <span className="pulse-dot" />
            {freshness}
          </div>

          <div className="node-chip">
            <Radio size={15} />
            {latest?.node_id || "UB-01"}
          </div>

          <button
            className="refresh-button"
            onClick={() => void loadData(true)}
            disabled={refreshing}
            aria-label="Refresh dashboard"
          >
            <RefreshCw
              size={17}
              className={refreshing ? "spin" : undefined}
            />
          </button>
        </div>
      </header>

      <section className={`hero-status ${status.className}`}>
        <div className="hero-left">
          <div className="eyebrow">CURRENT BRIDGE STATUS</div>

          <div className="status-row">
            <span className="status-indicator" />
            <span className="status-label">{status.label}</span>
          </div>

          <p className="status-description">
            {latest?.public_message || status.description}
          </p>

          <div className="updated-line">
            Last telemetry: {formatAge(latestAge)}
          </div>
        </div>

        <div className="clearance-display">
          <span className="clearance-label">Bridge clearance</span>
          <strong>
            {displayState === "UNKNOWN" && lastValid
              ? formatNumber(lastValid.clearance_cm)
              : formatNumber(latest?.clearance_cm)}
          </strong>
          <span className="clearance-unit">cm</span>

          {displayState === "UNKNOWN" && lastValid && (
            <span className="last-valid-note">Last valid measurement</span>
          )}
        </div>
      </section>

      {error && (
        <section className="system-banner">
          <WifiOff size={19} />
          <div>
            <strong>Dashboard data connection problem</strong>
            <span>{error}</span>
          </div>
        </section>
      )}

      <section className="metrics-grid">
        <MetricCard
          icon={<Gauge size={19} />}
          label="Clearance"
          value={`${formatNumber(latest?.clearance_cm)} cm`}
          subtext={
            finite(latest?.distance_cm)
              ? `Sensor distance ${latest.distance_cm.toFixed(1)} cm`
              : "Current measurement unavailable"
          }
        />

        <MetricCard
          icon={
            isRising ? (
              <ArrowDownRight size={19} />
            ) : isFalling ? (
              <ArrowUpRight size={19} />
            ) : (
              <Activity size={19} />
            )
          }
          label="Water Trend"
          value={
            isRising
              ? "Rising"
              : isFalling
                ? "Falling"
                : finite(riseRate)
                  ? "Stable"
                  : "Unknown"
          }
          subtext={
            finite(riseRate)
              ? `${Math.abs(riseRate).toFixed(2)} cm/min`
              : "Rise rate unavailable"
          }
        />

        <MetricCard
          icon={<Signal size={19} />}
          label="Sensor"
          value={latest?.sensor_status || "Unknown"}
          subtext={
            latest?.measurement_state === "OK"
              ? `Packet #${latest.packet_sequence ?? "—"}`
              : latest?.measurement_state || "No measurement state"
          }
        />

        <MetricCard
          icon={<Cloud size={19} />}
          label="Cloud Telemetry"
          value={freshness}
          subtext={`Updated ${formatAge(latestAge)}`}
        />
      </section>

      <section className="main-grid">
        <article className="panel chart-panel">
          <div className="panel-heading">
            <div>
              <span className="panel-kicker">MONITORING</span>
              <h2>Bridge Clearance Trend</h2>
            </div>
            <span className="time-range">24 HOURS</span>
          </div>

          <div className="chart-wrap">
            {chartData.length > 1 ? (
              <ResponsiveContainer width="100%" height="100%">
                <LineChart
                  data={chartData}
                  margin={{ top: 10, right: 14, left: -12, bottom: 0 }}
                >
                  <CartesianGrid
                    stroke="rgba(169,191,210,.18)"
                    vertical={false}
                  />
                  <XAxis
                    dataKey="time"
                    tick={{ fill: "#a9bfd2", fontSize: 11 }}
                    axisLine={false}
                    tickLine={false}
                    minTickGap={40}
                  />
                  <YAxis
                    tick={{ fill: "#a9bfd2", fontSize: 11 }}
                    axisLine={false}
                    tickLine={false}
                    width={55}
                    unit=" cm"
                  />
                  <Tooltip
                    contentStyle={{
                      background: "#102a40",
                      border: "1px solid #355b78",
                      borderRadius: 12,
                      color: "#f7fbff",
                    }}
                    formatter={(value) => [
                      `${Number(value).toFixed(1)} cm`,
                      "Clearance",
                    ]}
                  />
                  <Line
                    type="monotone"
                    dataKey="clearance"
                    stroke="#53d3ff"
                    strokeWidth={2.5}
                    dot={false}
                    activeDot={{ r: 4 }}
                    isAnimationActive={false}
                  />
                </LineChart>
              </ResponsiveContainer>
            ) : (
              <div className="empty-state">
                <Activity size={24} />
                <span>Waiting for enough valid telemetry to plot a trend.</span>
              </div>
            )}
          </div>
        </article>

        <article className="panel alert-panel">
          <div className="panel-heading">
            <div>
              <span className="panel-kicker">SAFETY</span>
              <h2>Current Alert</h2>
            </div>
          </div>

          {!currentAlert && displayState === "SAFE" ? (
            <div className="all-clear">
              <CheckCircle2 size={36} />
              <strong>No current safety alert</strong>
              <p>
                Current telemetry indicates normal bridge-access conditions.
              </p>
            </div>
          ) : (
            <div className="active-alert">
              <ShieldAlert size={34} />
              <strong>
                {displayState === "OFFLINE"
                  ? "Telemetry offline"
                  : latest?.alert_type ||
                    latest?.measurement_state ||
                    displayState}
              </strong>
              <p>
                {latest?.alert_message ||
                  latest?.sensor_error ||
                  status.description}
              </p>
            </div>
          )}
        </article>
      </section>

      <section className="secondary-grid">
        <article className="panel">
          <div className="panel-heading">
            <div>
              <span className="panel-kicker">SYSTEM</span>
              <h2>Device Health</h2>
            </div>
          </div>

          <div className="health-list">
            <div className="health-row">
              <span>
                <Signal size={17} /> Ultrasonic sensor
              </span>
              <strong
                className={
                  latest?.sensor_status === "OK" ? "ok-text" : "warn-text"
                }
              >
                {latest?.sensor_status || "Unknown"}
              </strong>
            </div>

            <div className="health-row">
              <span>
                <Cpu size={17} /> Measurement processing
              </span>
              <strong
                className={
                  latest?.measurement_state === "OK"
                    ? "ok-text"
                    : "warn-text"
                }
              >
                {latest?.measurement_state || "Unknown"}
              </strong>
            </div>

            <div className="health-row">
              <span>
                <Cloud size={17} /> Cloud data freshness
              </span>
              <strong
                className={
                  freshness === "LIVE" ? "ok-text" : "warn-text"
                }
              >
                {freshness}
              </strong>
            </div>

            <div className="health-row">
              <span>
                <Radio size={17} /> Node
              </span>
              <strong>{latest?.node_id || "UB-01"}</strong>
            </div>

            <div className="health-row">
              <span>
                <Activity size={17} /> Firmware
              </span>
              <strong>
                {latest?.fw_build || latest?.fw_profile || "—"}
              </strong>
            </div>
          </div>
        </article>

        <article className="panel">
          <div className="panel-heading">
            <div>
              <span className="panel-kicker">SENSOR DIAGNOSTICS</span>
              <h2>Latest Measurement</h2>
            </div>
          </div>

          <div className="diagnostic-grid">
            <div>
              <span>Raw distance</span>
              <strong>{formatNumber(latest?.raw_distance_cm)} cm</strong>
            </div>
            <div>
              <span>Accepted distance</span>
              <strong>{formatNumber(latest?.accepted_distance_cm)} cm</strong>
            </div>
            <div>
              <span>Candidate distance</span>
              <strong>{formatNumber(latest?.candidate_distance_cm)} cm</strong>
            </div>
            <div>
              <span>Confidence</span>
              <strong>
                {latest?.confidence_score != null
                  ? `${latest.confidence_score}%`
                  : "—"}
              </strong>
            </div>
          </div>
        </article>
      </section>

      <section className="panel events-panel">
        <div className="panel-heading">
          <div>
            <span className="panel-kicker">AUDIT TRAIL</span>
            <h2>Recent Events</h2>
          </div>
        </div>

        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Time</th>
                <th>Risk</th>
                <th>Clearance</th>
                <th>Sensor</th>
                <th>Measurement</th>
                <th>Packet</th>
              </tr>
            </thead>
            <tbody>
              {recentEvents.map((record) => (
                <tr key={record.id}>
                  <td>
                    {new Date(record.created_at).toLocaleTimeString([], {
                      hour: "2-digit",
                      minute: "2-digit",
                      second: "2-digit",
                    })}
                  </td>
                  <td>
                    <span
                      className={`risk-pill risk-${(
                        record.fused_risk || "unknown"
                      ).toLowerCase()}`}
                    >
                      {record.fused_risk || "UNKNOWN"}
                    </span>
                  </td>
                  <td>{formatNumber(record.clearance_cm)} cm</td>
                  <td>{record.sensor_status || "—"}</td>
                  <td>{record.measurement_state || "—"}</td>
                  <td>#{record.packet_sequence ?? "—"}</td>
                </tr>
              ))}

              {!loading && recentEvents.length === 0 && (
                <tr>
                  <td colSpan={6} className="no-records">
                    No RiverGuardian telemetry available yet.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>

      <footer>
        <span>RiverGuardian AI</span>
        <span>Edge-first bridge flood-access monitoring</span>
      </footer>
    </main>
  );
}



