import { createClient } from "npm:@supabase/supabase-js@2";

function resolveSecretKey(): string {
  const explicit =
    Deno.env.get("SUPABASE_SECRET_KEY") ||
    Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");

  if (explicit && explicit.trim().length > 0) {
    return explicit;
  }

  const secretKeysJson = Deno.env.get("SUPABASE_SECRET_KEYS");
  if (!secretKeysJson) {
    throw new Error("Missing SUPABASE secret key for Edge Function");
  }

  const parsed = JSON.parse(secretKeysJson) as Record<string, string>;
  const key = parsed.default;

  if (!key) {
    throw new Error("SUPABASE_SECRET_KEYS.default is missing");
  }

  return key;
}

export function getAdminClient() {
  const url = Deno.env.get("SUPABASE_URL");
  if (!url) {
    throw new Error("Missing SUPABASE_URL");
  }

  const key = resolveSecretKey();
  return createClient(url, key, {
    auth: { persistSession: false },
  });
}
