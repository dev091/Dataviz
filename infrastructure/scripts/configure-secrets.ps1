param(
  [string]$EnvFile = "apps/api/.env.staging",
  [switch]$Force
)

$ErrorActionPreference = "Stop"

function New-SecureSecret {
  param([int]$Length = 32)
  $bytes = New-Object byte[] $Length
  $rng = [System.Security.Cryptography.RNGCryptoServiceProvider]::Create()
  $rng.GetBytes($bytes)
  $rng.Dispose()
  return [Convert]::ToBase64String($bytes).Replace("+", "-").Replace("/", "_").TrimEnd('=')
}

if ((Test-Path $EnvFile) -and -not $Force) {
  Write-Warning "Secrets file $EnvFile already exists. Use -Force to overwrite."
  return
}

Write-Host "Generating production-grade secrets for staging..."
$jwtSecret = New-SecureSecret -Length 64
$stripeWebhook = "whsec_" + (New-SecureSecret -Length 32)
$apiKey = "sk_live_" + (New-SecureSecret -Length 32)

$envContent = @"
# Auto-generated staging secrets
JWT_SECRET_KEY=$jwtSecret
STRIPE_WEBHOOK_SECRET=$stripeWebhook
INTERNAL_API_KEY=$apiKey

# Database config
DATABASE_URL=postgresql://staging_user:staging_pass@localhost:5432/dataviz_staging
REDIS_URL=redis://localhost:6379/1

# Optional overrides
# OPENAI_API_KEY=
"@

$dir = Split-Path $EnvFile -Parent
if (-not [string]::IsNullOrWhiteSpace($dir)) {
  New-Item -ItemType Directory -Force -Path $dir | Out-Null
}

Set-Content -Path $EnvFile -Value $envContent -Encoding UTF8
Write-Host "Secrets generated and saved to $EnvFile" -ForegroundColor Green
