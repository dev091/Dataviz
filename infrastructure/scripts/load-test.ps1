param(
  [string]$Host = "http://localhost:8000",
  [int]$Users = 20,
  [int]$SpawnRate = 5,
  [string]$Duration = "2m"
)

$ErrorActionPreference = "Stop"

$locust = Get-Command locust -ErrorAction SilentlyContinue
if (-not $locust) {
  throw "locust is not installed. Install with: pip install locust"
}

Write-Host "Running load test against $Host"
locust -f infrastructure/perf/locustfile.py --headless --host $Host -u $Users -r $SpawnRate --run-time $Duration
