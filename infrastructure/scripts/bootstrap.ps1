param(
  [switch]$Install
)

if ($Install) {
  npm install
}

Write-Host "Start backend dependencies with: docker compose up -d postgres redis"
Write-Host "Install API deps: pip install -r apps/api/requirements.txt"
Write-Host "Run API: uvicorn app.main:app --reload --app-dir apps/api"
Write-Host "Run Worker: celery -A worker.celery_app worker --beat --loglevel=info --workdir apps/worker"
Write-Host "Run Web: npm run dev --workspace apps/web"
