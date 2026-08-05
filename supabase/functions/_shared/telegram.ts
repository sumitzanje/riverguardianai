export type TelegramInlineKeyboardButton = {
  text: string;
  callback_data?: string;
  url?: string;
};

export type TelegramApiResponse = {
  ok: boolean;
  result?: {
    message_id?: number;
  };
  description?: string;
};

function botToken(): string {
  const token = Deno.env.get("TELEGRAM_BOT_TOKEN");
  if (!token) {
    throw new Error("Missing TELEGRAM_BOT_TOKEN");
  }
  return token;
}

async function callTelegram(
  method: string,
  payload: Record<string, unknown>,
): Promise<TelegramApiResponse> {
  const url = `https://api.telegram.org/bot${botToken()}/${method}`;

  const response = await fetch(url, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(payload),
  });

  const text = await response.text();
  let parsed: TelegramApiResponse;

  try {
    parsed = JSON.parse(text) as TelegramApiResponse;
  } catch {
    parsed = { ok: false, description: text };
  }

  if (!response.ok || !parsed.ok) {
    throw new Error(
      `Telegram API ${method} failed: ${response.status} ${parsed.description ?? "unknown"}`,
    );
  }

  return parsed;
}

export async function sendTelegramMessage(
  chatId: number,
  text: string,
  keyboardRows?: TelegramInlineKeyboardButton[][],
): Promise<TelegramApiResponse> {
  const replyMarkup = keyboardRows
    ? { inline_keyboard: keyboardRows }
    : undefined;

  return await callTelegram("sendMessage", {
    chat_id: chatId,
    text,
    disable_web_page_preview: true,
    reply_markup: replyMarkup,
  });
}

export async function answerCallbackQuery(
  callbackQueryId: string,
  text = "Updated",
): Promise<void> {
  await callTelegram("answerCallbackQuery", {
    callback_query_id: callbackQueryId,
    text,
    show_alert: false,
  });
}

export function buildMainMenu(dashboardUrl: string): TelegramInlineKeyboardButton[][] {
  return [
    [
      { text: "Current Status", callback_data: "MENU_STATUS" },
      { text: "Recent Trend", callback_data: "MENU_TREND" },
    ],
    [
      { text: "Active Alerts", callback_data: "MENU_ALERTS" },
      { text: "Device Health", callback_data: "MENU_HEALTH" },
    ],
    [
      { text: "Alert Subscription", callback_data: "MENU_SUBSCRIBE" },
    ],
    [
      { text: "Open Dashboard", url: dashboardUrl },
      { text: "About RiverGuardian", callback_data: "MENU_ABOUT" },
    ],
  ];
}
