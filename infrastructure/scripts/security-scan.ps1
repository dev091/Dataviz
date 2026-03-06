param(
  [switch]$InstallTools
)

$ErrorActionPreference = "Stop"

$py = $env:PYTHON_EXE
if (-not $py) {
  $py = "C:\Users\rahul\AppData\Local\Programs\Python\Python311\python.exe"
}

if ($InstallTools) {
  & $py -m pip install --upgrade pip
  & $py -m pip install pip-audit
}

$pipAudit = Get-Command pip-audit -ErrorAction SilentlyContinue
if ($pipAudit) {
  Write-Host "Running pip-audit"
  pip-audit -r apps/api/requirements.txt
} else {
  Write-Warning "pip-audit not found. Run with -InstallTools to install it."
}

Write-Host "Running npm audit (high severity threshold)"
npm.cmd audit --audit-level=high
