import { getAdminClient } from "../_shared/supabase.ts";
import { sendTelegramMessage } from "../_shared/telegram.ts";

type WebhookPayload = {
  type?: string;
  table?: string;
  record?: Record<string, unknown>;
  old_record?: Record<string, unknown> | null;
};

function matchesAlertPreferences(
  subscriber: {
    receive_orange_alerts: boolean;
    receive_red_alerts: boolean;
    receive_device_alerts: boolean;
  },
  event: {
    recommendation_status?: string | null;
    alert_type?: string | null;
  },
): boolean {
  const risk = (event.recommendation_status ?? "").toUpperCase();
  const alertType = (event.alert_type ?? "").toUpperCase();

  if (risk === "RED") return subscriber.receive_red_alerts;
  if (risk === "ORANGE") return subscriber.receive_orange_alerts;

  const isDeviceAlert = ["SYSTEM_UNCERTAIN", "DEVICE_OFFLINE", "DEVICE_RECOVERED", "SENSOR_FAILURE"].includes(alertType);
  if (isDeviceAlert) return subscriber.receive_device_alerts;

  return subscriber.receive_device_alerts;
}

function formatAlertMessage(record: Record<string, unknown>): string {
  return [
    `RiverGuardian ${String(record.recommendation_status ?? record.fused_risk ?? "ALERT")} Alert`,
    `Site: ${String(record.site_id ?? "N/A")}`,
    `Node: ${String(record.node_id ?? "N/A")}`,
    `Water clearance: ${record.clearance_cm == null ? "N/A" : `${record.clearance_cm} cm`}`,
    `Rise rate: ${record.rise_rate_cm_min == null ? "N/A" : `${record.rise_rate_cm_min} cm/min`}`,
    `Estimated time to unsafe: ${record.time_to_unsafe_min == null ? "N/A" : `${Math.round(Number(record.time_to_unsafe_min))} min`}`,
    `Alert type: ${String(record.alert_type ?? "ALERT")}`,
    "",
    String(record.alert_message ?? "No alert message provided."),
  ].join("\n");
}

async function logDelivery(payload: {
  event_id: number;
  recipient_chat_id: number;
  message_type: string;
  delivery_status: string;
  failure_reason?: string | null;
  provider_message_id?: string | null;
}) {
  const supabase = getAdminClient();
  const { error } = await supabase.from("notification_deliveries").insert({
    event_id: payload.event_id,
    recipient_chat_id: payload.recipient_chat_id,
    platform: "TELEGRAM",
    message_type: payload.message_type,
    delivery_status: payload.delivery_status,
    failure_reason: payload.failure_reason ?? null,
    provider_message_id: payload.provider_message_id ?? null,
  });

  if (error) {
    console.error("delivery log insert failed", error.message);
  }
}

function validateDispatcherSecret(req: Request): void {
  const expected = Deno.env.get("ALERT_WEBHOOK_SECRET");
  if (!expected || expected.trim().length < 16) {
    throw new Error(
      "ALERT_WEBHOOK_SECRET is missing or too short. Refusing to run insecure dispatcher.",
    );
  }

  const received = req.headers.get("x-riverguardian-webhook-secret");
  if (!received || received !== expected) {
    throw new Response("Unauthorized", { status: 401 });
  }
}

Deno.serve(async (req) => {
  try {
    if (req.method !== "POST") {
      return new Response("Method Not Allowed", { status: 405 });
    }

    validateDispatcherSecret(req);

    const payload = (await req.json()) as WebhookPayload;
    const record = payload.record ?? {};

    if (payload.type !== "INSERT") {
      return new Response("ignored non-insert", { status: 200 });
    }

    if (String(payload.table ?? "") !== "riverguardian_events") {
      return new Response("ignored table", { status: 200 });
    }

    if (record.alert_should_send !== true) {
      return new Response("ignored non-alert", { status: 200 });
    }

    const supabase = getAdminClient();
    const { data: subscribers, error } = await supabase
      .from("telegram_subscribers")
      .select("chat_id,is_authorized,is_active,receive_orange_alerts,receive_red_alerts,receive_device_alerts")
      .eq("is_authorized", true)
      .eq("is_active", true);

    if (error) {
      throw new Error(`subscribers query failed: ${error.message}`);
    }

    const eventId = Number(record.id ?? 0);
    const message = formatAlertMessage(record);

    for (const subscriber of subscribers ?? []) {
      const chatId = Number(subscriber.chat_id);
      if (!matchesAlertPreferences(subscriber, {
        recommendation_status: String(record.recommendation_status ?? ""),
        alert_type: String(record.alert_type ?? ""),
      })) {
        continue;
      }

      try {
        const sendResult = await sendTelegramMessage(chatId, message);
        await logDelivery({
          event_id: eventId,
          recipient_chat_id: chatId,
          message_type: String(record.alert_type ?? "ALERT"),
          delivery_status: "SENT",
          provider_message_id: sendResult.result?.message_id
            ? String(sendResult.result.message_id)
            : null,
        });
      } catch (err) {
        await logDelivery({
          event_id: eventId,
          recipient_chat_id: chatId,
          message_type: String(record.alert_type ?? "ALERT"),
          delivery_status: "FAILED",
          failure_reason: err instanceof Error ? err.message : String(err),
        });
      }
    }

    return new Response("ok", { status: 200 });
  } catch (error) {
    if (error instanceof Response) {
      return error;
    }

    console.error("alert-dispatcher error", error);
    return new Response("error", { status: 500 });
  }
});
