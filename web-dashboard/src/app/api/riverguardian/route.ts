import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

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
    process.env.SUPABASE_SERVICE_ROLE_KEY ||
    process.env.SUPABASE_KEY;

  if (!supabaseUrl || !supabaseKey) {
    return NextResponse.json(
      {
        error:
          "Dashboard backend is not configured. SUPABASE_URL and a server-side Supabase key are required.",
      },
      { status: 503 }
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
    });

    if (!response.ok) {
      const details = await response.text();

      return NextResponse.json(
        {
          error: "Supabase request failed.",
          status: response.status,
          details,
        },
        { status: 502 }
      );
    }

    const records = await response.json();

    return NextResponse.json(
      {
        generated_at: new Date().toISOString(),
        records,
      },
      {
        headers: {
          "Cache-Control": "no-store, max-age=0",
        },
      }
    );
  } catch (error) {
    return NextResponse.json(
      {
        error: "Dashboard backend could not reach Supabase.",
        details: error instanceof Error ? error.message : String(error),
      },
      { status: 502 }
    );
  }
}
