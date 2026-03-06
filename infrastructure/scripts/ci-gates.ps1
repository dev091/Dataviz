$ErrorActionPreference = "Stop"

Write-Host "[1/4] Running backend test matrix"
powershell -ExecutionPolicy Bypass -File infrastructure/scripts/backend-tests.ps1

Write-Host "[2/4] Running frontend typecheck"
npm.cmd --workspace apps/web exec tsc --noEmit

Write-Host "[3/4] Running frontend build"
npm.cmd --workspace apps/web run build

Write-Host "[4/4] Running docker smoke health check"
docker compose up -d --build
try {
  $healthy = $false
  for ($i = 0; $i -lt 40; $i++) {
    try {
      $resp = Invoke-RestMethod -Uri "http://localhost:8000/health" -Method Get
      if ($resp.status -eq "ok") {
        $healthy = $true
        break
      }
    } catch {
      Start-Sleep -Seconds 3
    }
  }

  if (-not $healthy) {
    docker compose ps
    throw "API health check failed during smoke test"
  }

  Write-Host "CI gates passed"
}
finally {
  docker compose down -v
}
