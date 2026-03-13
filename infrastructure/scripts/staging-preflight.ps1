param(
  [string]$ApiBase = "http://localhost:8000",
  [string]$WebBase = "http://localhost:3000",
  [string]$Email = "",
  [string]$Password = "",
  [switch]$ValidateEnv,
  [switch]$RequireStripe,
  [string]$ReportPath = "infrastructure/tmp/staging-preflight.json"
)

$ErrorActionPreference = "Stop"

$results = New-Object System.Collections.Generic.List[object]
$failed = $false

function Add-Result {
  param(
    [string]$Name,
    [bool]$Passed,
    [string]$Detail
  )

  $script:results.Add([pscustomobject]@{
    name = $Name
    passed = $Passed
    detail = $Detail
    checked_at = (Get-Date).ToString("o")
  }) | Out-Null

  if (-not $Passed) {
    $script:failed = $true
    Write-Host "FAIL: $Name - $Detail" -ForegroundColor Red
  } else {
    Write-Host "PASS: $Name - $Detail" -ForegroundColor Green
  }
}

function Require-EnvVar {
  param([string]$Name)

  $value = [Environment]::GetEnvironmentVariable($Name)
  if ([string]::IsNullOrWhiteSpace($value)) {
    Add-Result -Name "env:$Name" -Passed:$false -Detail "Missing environment variable"
  } else {
    Add-Result -Name "env:$Name" -Passed:$true -Detail "Configured"
  }
}

function Invoke-WebRequestCompat {
  param(
    [Parameter(Mandatory = $true)]
    [string]$Uri,
    [string]$Method = "Get",
    [hashtable]$Headers = $null
  )

  $request = @{
    Uri = $Uri
    Method = $Method
  }

  if ($Headers) {
    $request.Headers = $Headers
  }

  if ($PSVersionTable.PSVersion.Major -lt 6) {
    $request.UseBasicParsing = $true
  }

  Invoke-WebRequest @request
}

if ($ValidateEnv) {
  Require-EnvVar -Name "DATABASE_URL"
  Require-EnvVar -Name "REDIS_URL"
  Require-EnvVar -Name "JWT_SECRET_KEY"

  $billingProvider = [Environment]::GetEnvironmentVariable("BILLING_PROVIDER")
  if ($RequireStripe -or $billingProvider -eq "stripe") {
    Require-EnvVar -Name "STRIPE_SECRET_KEY"
    Require-EnvVar -Name "STRIPE_WEBHOOK_SECRET"
    Require-EnvVar -Name "STRIPE_PRICE_STARTER"
    Require-EnvVar -Name "STRIPE_PRICE_GROWTH"
    Require-EnvVar -Name "STRIPE_PRICE_ENTERPRISE"
  }
}

try {
  $health = Invoke-RestMethod -Uri "$ApiBase/health" -Method Get
  Add-Result -Name "api:health" -Passed:($health.status -eq "ok") -Detail ($health | ConvertTo-Json -Compress)
} catch {
  Add-Result -Name "api:health" -Passed:$false -Detail $_.Exception.Message
}

try {
  $metrics = Invoke-WebRequestCompat -Uri "$ApiBase/metrics" -Method Get
  Add-Result -Name "api:metrics" -Passed:($metrics.Content -match "app_requests_total") -Detail "Metrics endpoint reachable"
} catch {
  Add-Result -Name "api:metrics" -Passed:$false -Detail $_.Exception.Message
}

try {
  $web = Invoke-WebRequestCompat -Uri $WebBase -Method Get
  Add-Result -Name "web:root" -Passed:($web.StatusCode -eq 200) -Detail "HTTP $($web.StatusCode)"
} catch {
  Add-Result -Name "web:root" -Passed:$false -Detail $_.Exception.Message
}

if ($Email) {
  if (-not $Password) {
    Add-Result -Name "auth:login" -Passed:$false -Detail "Password missing for authenticated checks"
  } else {
    try {
      $loginBody = @{ email = $Email; password = $Password } | ConvertTo-Json
      $login = Invoke-RestMethod -Uri "$ApiBase/api/v1/auth/login" -Method Post -ContentType "application/json" -Body $loginBody
      $workspaceId = $login.workspaces[0].workspace_id
      $headers = @{ Authorization = "Bearer $($login.access_token)"; "X-Workspace-Id" = $workspaceId }
      Add-Result -Name "auth:login" -Passed:$true -Detail "Workspace $workspaceId"

      try {
        $dashboards = Invoke-RestMethod -Uri "$ApiBase/api/v1/dashboards" -Headers $headers -Method Get
        Add-Result -Name "api:dashboards" -Passed:$true -Detail "Count=$($dashboards.Count)"
      } catch {
        Add-Result -Name "api:dashboards" -Passed:$false -Detail $_.Exception.Message
      }

      try {
        $models = Invoke-RestMethod -Uri "$ApiBase/api/v1/semantic/models" -Headers $headers -Method Get
        Add-Result -Name "api:semantic_models" -Passed:$true -Detail "Count=$($models.Count)"
      } catch {
        Add-Result -Name "api:semantic_models" -Passed:$false -Detail $_.Exception.Message
      }

      try {
        $subscription = Invoke-RestMethod -Uri "$ApiBase/api/v1/admin/subscription" -Headers $headers -Method Get
        Add-Result -Name "api:subscription" -Passed:$true -Detail "Plan=$($subscription.plan_tier) Status=$($subscription.subscription_status)"
      } catch {
        Add-Result -Name "api:subscription" -Passed:$false -Detail $_.Exception.Message
      }
    } catch {
      Add-Result -Name "auth:login" -Passed:$false -Detail $_.Exception.Message
    }
  }
}

New-Item -ItemType Directory -Force -Path (Split-Path $ReportPath -Parent) | Out-Null
$summary = [pscustomobject]@{
  api_base = $ApiBase
  web_base = $WebBase
  validated_env = [bool]$ValidateEnv
  require_stripe = [bool]$RequireStripe
  failed = $failed
  results = $results
}
$summary | ConvertTo-Json -Depth 6 | Set-Content -Path $ReportPath -Encoding UTF8
Write-Host "Preflight report written to $ReportPath"

if ($failed) {
  throw "Staging preflight failed"
}
