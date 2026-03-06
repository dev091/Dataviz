$ErrorActionPreference = "Stop"

$py = $env:PYTHON_EXE
if (-not $py) {
  $py = "C:\Users\rahul\AppData\Local\Programs\Python\Python311\python.exe"
}

Write-Host "Running env-gated live connector suite"
& $py -m pytest apps/api/tests/test_connectors_live.py -q
