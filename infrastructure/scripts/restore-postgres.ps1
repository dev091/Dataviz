param(
  [Parameter(Mandatory = $true)]
  [string]$BackupFile,
  [switch]$ResetSchema,
  [string]$DatabaseUrl = "",
  [string]$ContainerName = "analytics-postgres"
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $BackupFile)) {
  throw "Backup file not found: $BackupFile"
}

function Get-PsqlCommand {
  $psql = Get-Command psql -ErrorAction SilentlyContinue
  if ($psql) {
    return $psql.Source
  }
  return $null
}

function Reset-WithPsql {
  param([string]$ConnString)
  $psql = Get-PsqlCommand
  if (-not $psql) {
    return $false
  }

  Write-Host "Resetting public schema with psql"
  & $psql $ConnString -c "DROP SCHEMA IF EXISTS public CASCADE; CREATE SCHEMA public;"
  return $true
}

function Restore-WithPsql {
  param([string]$ConnString, [string]$SourceFile)
  $psql = Get-PsqlCommand
  if (-not $psql) {
    return $false
  }

  Write-Host "Restoring backup with psql from $SourceFile"
  Get-Content $SourceFile -Raw | & $psql $ConnString
  Write-Host "Verifying database connectivity after restore"
  & $psql $ConnString -c "SELECT 1;"
  return $true
}

function Reset-WithDocker {
  param([string]$PgContainer)
  $docker = Get-Command docker -ErrorAction SilentlyContinue
  if (-not $docker) {
    throw "Neither psql nor docker is available for restore"
  }

  Write-Host "Resetting public schema in docker container $PgContainer"
  & $docker.Source exec $PgContainer psql -U postgres -d analytics -c "DROP SCHEMA IF EXISTS public CASCADE; CREATE SCHEMA public;"
}

function Restore-WithDocker {
  param([string]$SourceFile, [string]$PgContainer)
  $docker = Get-Command docker -ErrorAction SilentlyContinue
  if (-not $docker) {
    throw "Neither psql nor docker is available for restore"
  }

  Write-Host "Restoring backup from $SourceFile into docker container $PgContainer"
  Get-Content $SourceFile -Raw | & $docker.Source exec -i $PgContainer psql -U postgres -d analytics
  & $docker.Source exec $PgContainer psql -U postgres -d analytics -c "SELECT 1;"
}

if ($DatabaseUrl) {
  if ($ResetSchema) {
    if (-not (Reset-WithPsql -ConnString $DatabaseUrl)) {
      throw "psql is required when DatabaseUrl is provided"
    }
  }

  if (-not (Restore-WithPsql -ConnString $DatabaseUrl -SourceFile $BackupFile)) {
    throw "psql is required when DatabaseUrl is provided"
  }
} else {
  if ($ResetSchema) {
    Reset-WithDocker -PgContainer $ContainerName
  }
  Restore-WithDocker -SourceFile $BackupFile -PgContainer $ContainerName
}

Write-Host "Restore complete"
