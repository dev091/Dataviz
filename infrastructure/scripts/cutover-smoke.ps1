param(
  [string]$ApiBase = "http://localhost:8000",
  [string]$WebBase = "http://localhost:3000"
)

$ErrorActionPreference = "Stop"

function Invoke-WebRequestCompat {
  param(
    [Parameter(Mandatory = $true)]
    [string]$Uri,
    [string]$Method = "Get"
  )

  $request = @{
    Uri = $Uri
    Method = $Method
  }

  if ($PSVersionTable.PSVersion.Major -lt 6) {
    $request.UseBasicParsing = $true
  }

  Invoke-WebRequest @request
}

Write-Host "Checking API health"
$health = Invoke-RestMethod -Uri "$ApiBase/health" -Method Get
if ($health.status -ne "ok") {
  throw "API health check failed"
}

Write-Host "Checking API metrics"
$metrics = Invoke-WebRequestCompat -Uri "$ApiBase/metrics" -Method Get
if (-not $metrics.Content.Contains("app_requests_total")) {
  throw "Metrics endpoint missing expected counters"
}

Write-Host "Checking web availability"
$web = Invoke-WebRequestCompat -Uri $WebBase -Method Get
if ($web.StatusCode -ne 200) {
  throw "Web app check failed"
}

Write-Host "Cutover smoke checks passed"
