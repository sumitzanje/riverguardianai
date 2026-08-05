import { ensureAdminBootstrap, isAuthorizedChat, upsertSubscriberSeen, validateTelegramWebhookSecret } from "../_shared/auth.ts";
import { formatAlertsMessage, formatHealthMessage, formatStatusMessage, formatTrendMessage } from "../_shared/formatters.ts";
import { getAdminClient } from "../_shared/supabase.ts";
import { answerCallbackQuery, buildMainMenu, sendTelegramMessage } from "../_shared/telegram.ts";

type TelegramUpdate = {
  message?: {
    text?: string;
    chat: {
      id: number;
      type?: string;
      username?: string;
      first_name?: string;
    };
  };
  callback_query?: {
    id: string;
    data?: string;
    message?: {
      chat: {
        id: number;
        type?: string;
        username?: string;
        first_name?: string;
      };
    };
  };
};

const DASHBOARD_URL = Deno.env.get("DASHBOARD_URL") ?? "https://supabase.com";
const STATUS_STALE_MIN = Number(Deno.env.get("STATUS_STALE_MIN") ?? "15");

function mainMenuText(): string {
  return [
    "RiverGuardian AI",
    "River monitoring system is online.",
    "Select an option:",
  ].join("\n");
}

async function fetchLatestRecord() {
  const supabase = getAdminClient();
  const { data, error } = await supabase
    .from("riverguardian_events")
    .select("id,created_at,node_id,site_id,fused_risk,recommendation_status,distance_cm,raw_distance_cm,accepted_distance_cm,candidate_distance_cm,sensor_status,measurement_state,sensor_error,packet_sequence,fw_profile,fw_build,clearance_cm,rise_rate_cm_min,time_to_unsafe_min,alert_type,alert_message")
    .order("created_at", { ascending: false })
    .limit(1)
    .maybeSingle();

  if (error) throw new Error(`status query failed: ${error.message}`);
  return data;
}

async function fetchTrendRows() {
  const supabase = getAdminClient();
  const since = new Date(Date.now() - 6 * 60 * 60 * 1000).toISOString();

  const { data, error } = await supabase
    .from("riverguardian_events")
    .select("id,created_at,node_id,site_id,fused_risk,recommendation_status,distance_cm,raw_distance_cm,accepted_distance_cm,candidate_distance_cm,sensor_status,measurement_state,sensor_error,packet_sequence,fw_profile,fw_build,clearance_cm,rise_rate_cm_min,time_to_unsafe_min,alert_type,alert_message")
    .gte("created_at", since)
    .order("created_at", { ascending: false })
    .limit(200);

  if (error) throw new Error(`trend query failed: ${error.message}`);
  return data ?? [];
}

async function fetchRecentAlerts() {
  const supabase = getAdminClient();
  const { data, error } = await supabase
    .from("riverguardian_events")
    .select("id,created_at,node_id,site_id,fused_risk,recommendation_status,distance_cm,raw_distance_cm,accepted_distance_cm,candidate_distance_cm,sensor_status,measurement_state,sensor_error,packet_sequence,fw_profile,fw_build,clearance_cm,rise_rate_cm_min,time_to_unsafe_min,alert_type,alert_message")
    .eq("alert_should_send", true)
    .order("created_at", { ascending: false })
    .limit(10);

  if (error) throw new Error(`alerts query failed: ${error.message}`);
  return data ?? [];
}

async function handleCommand(chatId: number, command: string): Promise<void> {
  const authorized = await isAuthorizedChat(chatId);

  if (command === "/subscribe") {
    if (authorized) {
      await sendTelegramMessage(chatId, "Subscription is already active.", buildMainMenu(DASHBOARD_URL));
      return;
    }

    await sendTelegramMessage(
      chatId,
      "Subscription request received. Please ask RiverGuardian admin to authorize this chat.",
    );
    return;
  }

  if (!authorized) {
    await sendTelegramMessage(
      chatId,
      "This chat is not authorized yet. Use /subscribe and ask admin for approval.",
    );
    return;
  }

  switch (command) {
    case "/start":
      await sendTelegramMessage(chatId, mainMenuText(), buildMainMenu(DASHBOARD_URL));
      break;
    case "/status": {
      const latest = await fetchLatestRecord();
      await sendTelegramMessage(chatId, formatStatusMessage(latest, STATUS_STALE_MIN), buildMainMenu(DASHBOARD_URL));
      break;
    }
    case "/trend": {
      const rows = await fetchTrendRows();
      await sendTelegramMessage(chatId, formatTrendMessage(rows), buildMainMenu(DASHBOARD_URL));
      break;
    }
    case "/alerts": {
      const rows = await fetchRecentAlerts();
      await sendTelegramMessage(chatId, formatAlertsMessage(rows), buildMainMenu(DASHBOARD_URL));
      break;
    }
    case "/health": {
      const latest = await fetchLatestRecord();
      await sendTelegramMessage(chatId, formatHealthMessage(latest, STATUS_STALE_MIN), buildMainMenu(DASHBOARD_URL));
      break;
    }
    case "/dashboard":
      await sendTelegramMessage(chatId, `Open dashboard: ${DASHBOARD_URL}`, buildMainMenu(DASHBOARD_URL));
      break;
    case "/help":
      await sendTelegramMessage(
        chatId,
        [
          "Commands:",
          "/start",
          "/status",
          "/trend",
          "/alerts",
          "/health",
          "/subscribe",
          "/dashboard",
          "/help",
        ].join("\n"),
        buildMainMenu(DASHBOARD_URL),
      );
      break;
    default:
      await sendTelegramMessage(chatId, "Unknown command. Use /help.", buildMainMenu(DASHBOARD_URL));
      break;
  }
}

async function handleCallback(chatId: number, callbackData: string): Promise<void> {
  switch (callbackData) {
    case "MENU_STATUS":
      await handleCommand(chatId, "/status");
      return;
    case "MENU_TREND":
      await handleCommand(chatId, "/trend");
      return;
    case "MENU_ALERTS":
      await handleCommand(chatId, "/alerts");
      return;
    case "MENU_HEALTH":
      await handleCommand(chatId, "/health");
      return;
    case "MENU_SUBSCRIBE":
      await handleCommand(chatId, "/subscribe");
      return;
    case "MENU_ABOUT":
      await sendTelegramMessage(
        chatId,
        "RiverGuardian AI is an edge-first flood-access monitoring system for river bridge safety.",
        buildMainMenu(DASHBOARD_URL),
      );
      return;
    default:
      await sendTelegramMessage(chatId, "Unknown menu action.", buildMainMenu(DASHBOARD_URL));
      return;
  }
}

Deno.serve(async (req) => {
  try {
    validateTelegramWebhookSecret(req);

    const update = (await req.json()) as TelegramUpdate;

    if (update.message?.chat) {
      const chat = update.message.chat;
      await ensureAdminBootstrap(chat);
      await upsertSubscriberSeen(chat);

      const command = (update.message.text ?? "").trim().split(" ")[0];
      await handleCommand(chat.id, command || "/start");

      return new Response("ok", { status: 200 });
    }

    if (update.callback_query?.message?.chat) {
      const callback = update.callback_query;
      const chat = callback.message.chat;

      await ensureAdminBootstrap(chat);
      await upsertSubscriberSeen(chat);
      await answerCallbackQuery(callback.id, "Updated");

      await handleCallback(chat.id, callback.data ?? "");
      return new Response("ok", { status: 200 });
    }

    return new Response("ignored", { status: 200 });
  } catch (error) {
    if (error instanceof Response) {
      return error;
    }

    console.error("telegram-webhook error", error);
    return new Response("error", { status: 500 });
  }
});



