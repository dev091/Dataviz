param(
  [string]$ApiBase = "http://localhost:8000",
  [string]$WebBase = "http://localhost:3000",
  [string]$Email = "",
  [string]$Password = "",
  [switch]$ValidateEnv,
  [switch]$RequireStripe,
  [switch]$IncludeBilling,
  [switch]$IncludeConnectors,
  [switch]$IncludeLoad,
  [ValidateSet("starter", "growth", "enterprise")]
  [string]$PlanTier = "growth",
  [switch]$SkipPortal,
  [switch]$SimulateStripeWebhook,
  [string]$StripeWebhookSecret = "",
  [int]$LoadUsers = 20,
  [int]$LoadSpawnRate = 5,
  [string]$LoadDuration = "2m",
  [string]$LoadQuestion = "show monthly revenue by region",
  [string]$ReportPath = "infrastructure/tmp/ops-verify/summary.json"
)

$ErrorActionPreference = "Stop"
$powerShellExe = (Get-Command powershell.exe -ErrorAction Stop).Source
$artifactRoot = Split-Path $ReportPath -Parent
New-Item -ItemType Directory -Force -Path $artifactRoot | Out-Null

$stages = New-Object System.Collections.Generic.List[object]

function Read-JsonIfExists {
  param([string]$Path)

  if ($Path -and (Test-Path $Path)) {
    return Get-Content $Path -Raw | ConvertFrom-Json
  }

  return $null
}

function Invoke-Stage {
  param(
    [Parameter(Mandatory = $true)]
    [string]$Name,
    [Parameter(Mandatory = $true)]
    [string]$FilePath,
    [string[]]$Arguments = @(),
    [string]$ArtifactPath = ""
  )

  Write-Host "Running stage: $Name"
  & $powerShellExe -ExecutionPolicy Bypass -File $FilePath @Arguments
  if ($LASTEXITCODE -ne 0) {
    throw "Stage failed: $Name"
  }

  $data = Read-JsonIfExists -Path $ArtifactPath
  $stages.Add([pscustomobject]@{
    name = $Name
    artifact_path = $ArtifactPath
    completed_at = (Get-Date).ToString("o")
    data = $data
  }) | Out-Null
}

$preflightReport = Join-Path $artifactRoot "preflight.json"
$preflightArgs = @(
  "-ApiBase", $ApiBase,
  "-WebBase", $WebBase,
  "-ReportPath", $preflightReport
)
if ($Email) {
  if (-not $Password) {
    throw "Password is required when Email is provided"
  }
  $preflightArgs += @("-Email", $Email, "-Password", $Password)
}
if ($ValidateEnv) {
  $preflightArgs += "-ValidateEnv"
}
if ($RequireStripe) {
  $preflightArgs += "-RequireStripe"
}
Invoke-Stage -Name "preflight" -FilePath "infrastructure/scripts/staging-preflight.ps1" -Arguments $preflightArgs -ArtifactPath $preflightReport

Invoke-Stage -Name "cutover_smoke" -FilePath "infrastructure/scripts/cutover-smoke.ps1" -Arguments @("-ApiBase", $ApiBase, "-WebBase", $WebBase)

if ($IncludeBilling) {
  if (-not $Email -or -not $Password) {
    throw "Billing verification requires Email and Password"
  }

  $billingReport = Join-Path $artifactRoot "billing-smoke.json"
  $billingArgs = @(
    "-ApiBase", $ApiBase,
    "-Email", $Email,
    "-Password", $Password,
    "-PlanTier", $PlanTier,
    "-ReportPath", $billingReport
  )
  if ($SkipPortal) {
    $billingArgs += "-SkipPortal"
  }
  if ($SimulateStripeWebhook) {
    $billingArgs += "-SimulateStripeWebhook"
    if ($StripeWebhookSecret) {
      $billingArgs += @("-StripeWebhookSecret", $StripeWebhookSecret)
    }
  }

  Invoke-Stage -Name "billing_smoke" -FilePath "infrastructure/scripts/billing-smoke.ps1" -Arguments $billingArgs -ArtifactPath $billingReport
}

if ($IncludeLoad) {
  $loadDir = Join-Path $artifactRoot "load-test"
  $loadArgs = @(
    "-ApiBase", $ApiBase,
    "-Users", $LoadUsers,
    "-SpawnRate", $LoadSpawnRate,
    "-Duration", $LoadDuration,
    "-Question", $LoadQuestion,
    "-ReportDir", $loadDir
  )
  if ($Email) {
    $loadArgs += @("-Email", $Email, "-Password", $Password)
  }

  $loadSummary = Join-Path $loadDir "summary.json"
  Invoke-Stage -Name "load_test" -FilePath "infrastructure/scripts/load-test.ps1" -Arguments $loadArgs -ArtifactPath $loadSummary
}

if ($IncludeConnectors) {
  Invoke-Stage -Name "live_connectors" -FilePath "infrastructure/scripts/live-connectors.ps1"
}

$summary = [pscustomobject]@{
  api_base = $ApiBase
  web_base = $WebBase
  include_billing = [bool]$IncludeBilling
  include_connectors = [bool]$IncludeConnectors
  include_load = [bool]$IncludeLoad
  generated_at = (Get-Date).ToString("o")
  stages = $stages
}

$summary | ConvertTo-Json -Depth 8 | Set-Content -Path $ReportPath -Encoding UTF8
Write-Host "Verification summary written to $ReportPath"
