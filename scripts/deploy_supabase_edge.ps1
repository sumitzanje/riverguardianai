param(
    [Parameter(Mandatory = $true)]
    [string]$ProjectRef,

    [Parameter(Mandatory = $false)]
    [string]$AccessToken = ""
)

$ErrorActionPreference = "Stop"

if (-not (Get-Command supabase.cmd -ErrorAction SilentlyContinue)) {
    throw "supabase.cmd is not available. Install Supabase CLI first."
}

if ($AccessToken) {
    $env:SUPABASE_ACCESS_TOKEN = $AccessToken
}

if (-not $env:SUPABASE_ACCESS_TOKEN) {
    throw "SUPABASE_ACCESS_TOKEN is missing. Export it in this shell or pass -AccessToken."
}

Write-Host "Linking project $ProjectRef..."
supabase.cmd link --project-ref $ProjectRef

Write-Host "Applying database migrations..."
supabase.cmd db push

Write-Host "Deploying telegram-webhook..."
supabase.cmd functions deploy telegram-webhook

Write-Host "Deploying alert-dispatcher..."
supabase.cmd functions deploy alert-dispatcher

Write-Host "Done. Next: set Telegram webhook URL and configure Supabase Database Webhook."
