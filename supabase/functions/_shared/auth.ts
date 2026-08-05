import { getAdminClient } from "./supabase.ts";

type TelegramChat = {
  id: number;
  type?: string;
  username?: string;
  first_name?: string;
};

export function validateTelegramWebhookSecret(req: Request): void {
  const expected = Deno.env.get("TELEGRAM_WEBHOOK_SECRET");
  if (!expected) {
    throw new Error("Missing TELEGRAM_WEBHOOK_SECRET");
  }

  const received = req.headers.get("x-telegram-bot-api-secret-token");
  if (!received || received !== expected) {
    throw new Response("Unauthorized", { status: 401 });
  }
}

export async function ensureAdminBootstrap(chat: TelegramChat): Promise<void> {
  const adminChatRaw = Deno.env.get("TELEGRAM_ADMIN_CHAT_ID");
  if (!adminChatRaw) {
    throw new Error("Missing TELEGRAM_ADMIN_CHAT_ID");
  }

  const adminChatId = Number(adminChatRaw);
  if (chat.id !== adminChatId) {
    return;
  }

  const supabase = getAdminClient();

  const { error } = await supabase.from("telegram_subscribers").upsert(
    {
      chat_id: chat.id,
      chat_type: chat.type ?? "private",
      telegram_username: chat.username ?? null,
      first_name: chat.first_name ?? null,
      role: "ADMIN",
      is_authorized: true,
      is_active: true,
      receive_orange_alerts: true,
      receive_red_alerts: true,
      receive_device_alerts: true,
    },
    { onConflict: "chat_id" },
  );

  if (error) {
    throw new Error(`Failed to bootstrap admin subscriber: ${error.message}`);
  }
}

export async function upsertSubscriberSeen(chat: TelegramChat): Promise<void> {
  const supabase = getAdminClient();

  const { error } = await supabase.from("telegram_subscribers").upsert(
    {
      chat_id: chat.id,
      chat_type: chat.type ?? "private",
      telegram_username: chat.username ?? null,
      first_name: chat.first_name ?? null,
      is_active: true,
    },
    { onConflict: "chat_id" },
  );

  if (error) {
    throw new Error(`Failed to upsert subscriber: ${error.message}`);
  }
}

export async function isAuthorizedChat(chatId: number): Promise<boolean> {
  const supabase = getAdminClient();

  const { data, error } = await supabase
    .from("telegram_subscribers")
    .select("chat_id,is_authorized,is_active")
    .eq("chat_id", chatId)
    .maybeSingle();

  if (error) {
    throw new Error(`Failed to query chat authorization: ${error.message}`);
  }

  return !!data && data.is_authorized === true && data.is_active === true;
}
