param(
  [switch]$Pull,
  [switch]$DownFirst
)

$ErrorActionPreference = "Stop"

$rootDir = Split-Path $MyInvocation.MyCommand.Path -Parent | Split-Path -Parent | Split-Path -Parent
Set-Location $rootDir

if (-not (Test-Path "infrastructure/docker/docker-compose.yml")) {
    # If there's no compose file, we just run raw docker commands for Postgres and Redis
    Write-Host "No docker-compose.yml found, starting standalone Postgres and Redis containers..."

    if ($DownFirst) {
        docker rm -f dataviz-postgres-staging dataviz-redis-staging 2>$null
    }

    if ($Pull) {
        docker pull postgres:15-alpine
        docker pull redis:7-alpine
    }

    $pgRunning = docker ps -q -f name=dataviz-postgres-staging
    if (-not $pgRunning) {
        Write-Host "Starting Postgres..."
        docker run -d --name dataviz-postgres-staging `
            -e POSTGRES_USER=staging_user `
            -e POSTGRES_PASSWORD=staging_pass `
            -e POSTGRES_DB=dataviz_staging `
            -p 5432:5432 `
            postgres:15-alpine
    } else {
        Write-Host "Postgres already running."
    }

    $redisRunning = docker ps -q -f name=dataviz-redis-staging
    if (-not $redisRunning) {
        Write-Host "Starting Redis..."
        docker run -d --name dataviz-redis-staging `
            -p 6379:6379 `
            redis:7-alpine
    } else {
        Write-Host "Redis already running."
    }

    Write-Host "Staging infrastructure deployed successfully." -ForegroundColor Green
    return
}

# Assume docker-compose exists
Write-Host "Deploying staging infrastructure via docker-compose..."

if ($DownFirst) {
    docker-compose -f infrastructure/docker/docker-compose.yml down -v
}

if ($Pull) {
    docker-compose -f infrastructure/docker/docker-compose.yml pull
}

docker-compose -f infrastructure/docker/docker-compose.yml up -d

Write-Host "Staging infrastructure deployed successfully." -ForegroundColor Green
