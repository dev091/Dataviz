$ErrorActionPreference = "Stop"

$py = $env:PYTHON_EXE
if (-not $py) {
  $py = "C:\Users\rahul\AppData\Local\Programs\Python\Python311\python.exe"
}

Write-Host "[1/3] Running core backend flow tests"
& $py -m pytest apps/api/tests/test_core_flow.py apps/api/tests/test_report_delivery.py -q

Write-Host "[2/3] Running semantic and runtime hardening tests"
& $py -m pytest apps/api/tests/test_semantic_sql_builder.py apps/api/tests/test_runtime_hardening.py -q

Write-Host "[3/3] Running env-gated live connector suite"
& $py -m pytest apps/api/tests/test_connectors_live.py -q
