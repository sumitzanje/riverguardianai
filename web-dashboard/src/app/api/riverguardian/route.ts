import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

const SUPABASE_TIMEOUT_MS = 10_000;

const NO_STORE_HEADERS = {
  "Cache-Control": "no-store, max-age=0, must-revalidate",
};

const SELECT_FIELDS = [
  "id",
  "created_at",
  "local_record_id",
  "device_id",
  "site_id",
  "node_id",
  "distance_cm",
  "raw_distance_cm",
  "accepted_distance_cm",
  "candidate_distance_cm",
  "sensor_status",
  "measurement_state",
  "sensor_error",
  "packet_sequence",
  "fw_profile",
  "fw_build",
  "clearance_cm",
  "rise_rate_cm_min",
  "rise_acceleration_cm_min2",
  "time_to_unsafe_min",
  "base_risk",
  "fused_risk",
  "rainfall_class",
  "rain_hourly_mm",
  "rain_daily_mm",
  "confidence_score",
  "confidence_level",
  "recommendation_status",
  "public_message",
  "technical_summary",
  "action_level",
  "dashboard_priority",
  "alert_should_send",
  "alert_type",
  "alert_reason",
  "alert_message",
  "source",
  "payload_version",
].join(",");

export async function GET() {
  const supabaseUrl = process.env.SUPABASE_URL?.replace(/\/$/, "");
  const supabaseKey =
    process.env.SUPABASE_SECRET_KEY ||
    process.env.SUPABASE_SERVICE_ROLE_KEY;

  if (!supabaseUrl || !supabaseKey) {
    console.error("RiverGuardian dashboard backend is missing Supabase configuration.");

    return NextResponse.json(
      {
        error: "Dashboard backend is temporarily unavailable.",
      },
      {
        status: 503,
        headers: NO_STORE_HEADERS,
      }
    );
  }

  const endpoint =
    `${supabaseUrl}/rest/v1/riverguardian_events` +
    `?select=${encodeURIComponent(SELECT_FIELDS)}` +
    `&order=created_at.desc&limit=300`;

  try {
    const response = await fetch(endpoint, {
      headers: {
        apikey: supabaseKey,
        Authorization: `Bearer ${supabaseKey}`,
        Accept: "application/json",
      },
      cache: "no-store",
      signal: AbortSignal.timeout(SUPABASE_TIMEOUT_MS),
    });

    if (!response.ok) {
      console.error("RiverGuardian Supabase request failed.", {
        status: response.status,
      });

      return NextResponse.json(
        {
          error: "Telemetry service temporarily unavailable.",
        },
        {
          status: 502,
          headers: NO_STORE_HEADERS,
        }
      );
    }

    const records: unknown = await response.json();

    if (!Array.isArray(records)) {
      console.error("RiverGuardian Supabase returned an unexpected response.");

      return NextResponse.json(
        {
          error: "Telemetry service returned an invalid response.",
        },
        {
          status: 502,
          headers: NO_STORE_HEADERS,
        }
      );
    }

    return NextResponse.json(
      {
        generated_at: new Date().toISOString(),
        records,
      },
      {
        headers: NO_STORE_HEADERS,
      }
    );
  } catch (error) {
    const timedOut =
      error instanceof DOMException && error.name === "TimeoutError";

    console.error(
      timedOut
        ? "RiverGuardian Supabase request timed out."
        : "RiverGuardian Supabase request failed unexpectedly."
    );

    return NextResponse.json(
      {
        error: timedOut
          ? "Telemetry service timed out."
          : "Telemetry service temporarily unavailable.",
      },
      {
        status: timedOut ? 504 : 502,
        headers: NO_STORE_HEADERS,
      }
    );
  }
}
