param(
  [string]$ApiBase = "http://localhost:8000",
  [Parameter(Mandatory = $true)]
  [string]$Email,
  [Parameter(Mandatory = $true)]
  [string]$Password,
  [ValidateSet("starter", "growth", "enterprise")]
  [string]$PlanTier = "growth",
  [switch]$SkipPortal,
  [switch]$SimulateStripeWebhook,
  [string]$StripeWebhookSecret = "",
  [string]$ReportPath = "infrastructure/tmp/billing-smoke.json"
)

$ErrorActionPreference = "Stop"

function New-Signature {
  param(
    [string]$Secret,
    [string]$Payload
  )

  $timestamp = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds().ToString()
  $bytes = [Text.Encoding]::UTF8.GetBytes("$timestamp.$Payload")
  $key = [Text.Encoding]::UTF8.GetBytes($Secret)
  $hmac = [System.Security.Cryptography.HMACSHA256]::new($key)
  try {
    $hash = [BitConverter]::ToString($hmac.ComputeHash($bytes)).Replace("-", "").ToLowerInvariant()
    return "t=$timestamp,v1=$hash"
  } finally {
    $hmac.Dispose()
  }
}

$loginBody = @{ email = $Email; password = $Password } | ConvertTo-Json
$login = Invoke-RestMethod -Uri "$ApiBase/api/v1/auth/login" -Method Post -ContentType "application/json" -Body $loginBody
$workspaceId = $login.workspaces[0].workspace_id
$headers = @{ Authorization = "Bearer $($login.access_token)"; "X-Workspace-Id" = $workspaceId }

$before = Invoke-RestMethod -Uri "$ApiBase/api/v1/admin/subscription" -Headers $headers -Method Get
$checkout = Invoke-RestMethod -Uri "$ApiBase/api/v1/billing/checkout-session" -Headers $headers -Method Post -ContentType "application/json" -Body (@{ plan_tier = $PlanTier } | ConvertTo-Json)
$afterCheckout = Invoke-RestMethod -Uri "$ApiBase/api/v1/admin/subscription" -Headers $headers -Method Get

$portal = $null
if (-not $SkipPortal) {
  $portal = Invoke-RestMethod -Uri "$ApiBase/api/v1/billing/portal-session" -Headers $headers -Method Post -ContentType "application/json" -Body (@{} | ConvertTo-Json)
}

$webhookResult = $null
if ($SimulateStripeWebhook) {
  if ([string]::IsNullOrWhiteSpace($StripeWebhookSecret)) {
    throw "StripeWebhookSecret is required when SimulateStripeWebhook is enabled"
  }

  $customerId = $checkout.organization.billing_customer_id
  $priceId = $checkout.organization.billing_price_id
  if ([string]::IsNullOrWhiteSpace($priceId)) {
    switch ($PlanTier) {
      "starter" { $priceId = "price_starter" }
      "growth" { $priceId = "price_growth" }
      "enterprise" { $priceId = "price_enterprise" }
    }
  }

  $payload = @{
    type = "customer.subscription.updated"
    data = @{
      object = @{
        object = "subscription"
        id = "sub_smoke_$(Get-Random -Minimum 1000 -Maximum 9999)"
        customer = $customerId
        status = "active"
        items = @{ data = @(@{ price = @{ id = $priceId } }) }
      }
    }
  } | ConvertTo-Json -Depth 8 -Compress

  $signature = New-Signature -Secret $StripeWebhookSecret -Payload $payload
  $webhookHeaders = @{ "Stripe-Signature" = $signature }
  $webhookResult = Invoke-RestMethod -Uri "$ApiBase/api/v1/billing/webhooks/stripe" -Method Post -ContentType "application/json" -Headers $webhookHeaders -Body $payload
}

$after = Invoke-RestMethod -Uri "$ApiBase/api/v1/admin/subscription" -Headers $headers -Method Get
$result = [pscustomobject]@{
  workspace_id = $workspaceId
  before = $before
  checkout = $checkout
  portal = $portal
  webhook = $webhookResult
  after = $after
}

New-Item -ItemType Directory -Force -Path (Split-Path $ReportPath -Parent) | Out-Null
$result | ConvertTo-Json -Depth 8 | Set-Content -Path $ReportPath -Encoding UTF8
Write-Host "Billing smoke report written to $ReportPath"

if (-not $checkout.url) {
  throw "Checkout session did not return a URL"
}

if (-not $SkipPortal -and -not $portal.url) {
  throw "Billing portal session did not return a URL"
}

if ($SimulateStripeWebhook -and $after.subscription_status -ne "active") {
  throw "Webhook simulation did not result in an active subscription"
}
