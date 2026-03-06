param(
  [string]$OutputDir = "infrastructure/backups"
)

$ErrorActionPreference = "Stop"
New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null

$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$file = Join-Path $OutputDir "analytics-backup-$timestamp.sql"

Write-Host "Creating Postgres backup at $file"
docker exec analytics-postgres pg_dump -U postgres analytics | Set-Content -Encoding UTF8 $file

Write-Host "Backup complete: $file"
