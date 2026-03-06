param(
  [Parameter(Mandatory = $true)]
  [string]$BackupFile,
  [switch]$ResetSchema
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $BackupFile)) {
  throw "Backup file not found: $BackupFile"
}

if ($ResetSchema) {
  Write-Host "Resetting public schema"
  docker exec analytics-postgres psql -U postgres -d analytics -c "DROP SCHEMA IF EXISTS public CASCADE; CREATE SCHEMA public;"
}

Write-Host "Restoring backup from $BackupFile"
Get-Content $BackupFile -Raw | docker exec -i analytics-postgres psql -U postgres -d analytics

Write-Host "Restore complete"
