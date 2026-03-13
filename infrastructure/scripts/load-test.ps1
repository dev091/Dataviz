param(
  [string]$ApiBase = "http://localhost:8000",
  [int]$Users = 20,
  [int]$SpawnRate = 5,
  [string]$Duration = "2m",
  [string]$Email = "",
  [string]$Password = "",
  [string]$Question = "show monthly revenue by region",
  [string]$ReportDir = "infrastructure/tmp/load-test"
)

$ErrorActionPreference = "Stop"

function Resolve-LocustRunner {
  $locust = Get-Command locust -ErrorAction SilentlyContinue
  if ($locust) {
    return @{ type = "command"; value = $locust.Source }
  }

  $scriptsLocust = "C:\Users\rahul\AppData\Local\Programs\Python\Python311\Scripts\locust.exe"
  if (Test-Path $scriptsLocust) {
    return @{ type = "command"; value = $scriptsLocust }
  }

  $py = $env:PYTHON_EXE
  if (-not $py) {
    $py = "C:\Users\rahul\AppData\Local\Programs\Python\Python311\python.exe"
  }

  if (-not (Test-Path $py)) {
    throw "locust is not installed and PYTHON_EXE is not configured"
  }

  return @{ type = "python"; value = $py }
}

$runner = Resolve-LocustRunner

if ($Email -and -not $Password) {
  throw "Password is required when Email is provided"
}

New-Item -ItemType Directory -Force -Path $ReportDir | Out-Null
$csvPrefix = Join-Path $ReportDir "results"
$statsCsv = "${csvPrefix}_stats.csv"
$failuresCsv = "${csvPrefix}_failures.csv"
$historyCsv = "${csvPrefix}_stats_history.csv"
$exceptionsCsv = "${csvPrefix}_exceptions.csv"
$htmlReport = Join-Path $ReportDir "report.html"
$summaryJson = Join-Path $ReportDir "summary.json"

$env:DEMO_EMAIL = $Email
$env:DEMO_PASSWORD = $Password
$env:LOAD_TEST_QUESTION = $Question

Write-Host "Running load test against $ApiBase"
if ($Email) {
  Write-Host "Authenticated load profile enabled for $Email"
} else {
  Write-Host "Anonymous load profile only (health/metrics/openapi)"
}

$args = @(
  "-f", "infrastructure/perf/locustfile.py",
  "--headless",
  "--host", $ApiBase,
  "-u", $Users,
  "-r", $SpawnRate,
  "--run-time", $Duration,
  "--csv", $csvPrefix,
  "--csv-full-history",
  "--html", $htmlReport
)

if ($runner.type -eq "command") {
  & $runner.value @args
} else {
  & $runner.value -m locust @args
}

$aggregate = $null
if (Test-Path $statsCsv) {
  $aggregate = Import-Csv $statsCsv | Where-Object { $_.Name -eq "Aggregated" } | Select-Object -First 1
}

if ($aggregate) {
  $summary = [pscustomobject]@{
    api_base = $ApiBase
    users = $Users
    spawn_rate = $SpawnRate
    duration = $Duration
    authenticated = [bool]$Email
    request_count = [int]$aggregate.'Request Count'
    failure_count = [int]$aggregate.'Failure Count'
    requests_per_second = [double]$aggregate.'Requests/s'
    median_response_time_ms = [double]$aggregate.'Median Response Time'
    average_response_time_ms = [double]$aggregate.'Average Response Time'
    p95_response_time_ms = [double]$aggregate.'95%'
    max_response_time_ms = [double]$aggregate.'Max Response Time'
    stats_csv = $statsCsv
    failures_csv = $failuresCsv
    history_csv = $historyCsv
    exceptions_csv = $exceptionsCsv
    html_report = $htmlReport
  }
  $summary | ConvertTo-Json -Depth 4 | Set-Content -Path $summaryJson -Encoding UTF8
  Write-Host "Load summary written to $summaryJson"
  Write-Host ("Aggregated: requests={0} failures={1} rps={2} p95={3}ms" -f $summary.request_count, $summary.failure_count, $summary.requests_per_second, $summary.p95_response_time_ms)
}

Write-Host "Load test artifacts written to $ReportDir"
Write-Host "Stats CSV: $statsCsv"
Write-Host "History CSV: $historyCsv"
Write-Host "HTML report: $htmlReport"
