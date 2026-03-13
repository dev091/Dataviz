param(
  [string]$OutputDir = "infrastructure/backups",
  [string]$OutputFile = "",
  [string]$DatabaseUrl = "",
  [string]$ContainerName = "analytics-postgres"
)

$ErrorActionPreference = "Stop"
New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null

if (-not $OutputFile) {
  $timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
  $OutputFile = Join-Path $OutputDir "analytics-backup-$timestamp.sql"
}

function Backup-WithPgDump {
  param([string]$ConnString, [string]$TargetFile)

  $pgDump = Get-Command pg_dump -ErrorAction SilentlyContinue
  if (-not $pgDump) {
    return $false
  }

  Write-Host "Creating Postgres backup with pg_dump at $TargetFile"
  & $pgDump.Source --dbname=$ConnString --file=$TargetFile --no-owner --no-privileges
  return $true
}

function Backup-WithDocker {
  param([string]$TargetFile, [string]$PgContainer)

  $docker = Get-Command docker -ErrorAction SilentlyContinue
  if (-not $docker) {
    throw "Neither pg_dump nor docker is available for backup"
  }

  Write-Host "Creating Postgres backup from docker container $PgContainer at $TargetFile"
  & $docker.Source exec $PgContainer pg_dump -U postgres analytics | Set-Content -Encoding UTF8 $TargetFile
}

if ($DatabaseUrl) {
  if (-not (Backup-WithPgDump -ConnString $DatabaseUrl -TargetFile $OutputFile)) {
    throw "pg_dump is required when DatabaseUrl is provided"
  }
} else {
  Backup-WithDocker -TargetFile $OutputFile -PgContainer $ContainerName
}

Write-Host "Backup complete: $OutputFile"
