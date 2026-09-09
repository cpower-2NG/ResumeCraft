param(
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$webDir = Join-Path $root "web"
$python = Join-Path $root ".venv\Scripts\python.exe"
$backendUrl = "http://127.0.0.1:8000/api/health"
$webUrl = "http://127.0.0.1:5173"
$logDir = Join-Path $root "data\logs"

function Test-Url([string]$Url) {
    try {
        $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 2
        return $response.StatusCode -ge 200 -and $response.StatusCode -lt 400
    } catch {
        return $false
    }
}

function Wait-ForUrl([string]$Url, [string]$Name) {
    for ($attempt = 1; $attempt -le 30; $attempt++) {
        if (Test-Url $Url) {
            return
        }
        Start-Sleep -Seconds 1
    }
    throw "$Name did not become available. Check the logs in $logDir."
}

function Assert-PortAvailable([int]$Port, [string]$Name) {
    $listener = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue
    if ($listener) {
        throw "$Name port $Port is already in use, but the expected service is not responding. Close the program using that port and run this launcher again."
    }
}

Set-Location $root

# A complete running workbench needs both the SPA and its API. Do this before
# any setup work so a second launch only opens the existing application.
if ((Test-Url $webUrl) -and (Test-Url $backendUrl)) {
    Write-Host "Resume Workbench is already running at $webUrl"
    if (-not $NoBrowser) {
        Start-Process $webUrl
    }
    exit 0
}

if (-not (Test-Path $python)) {
    Write-Host "Creating Python virtual environment..."
    & python -m venv .venv
}

Write-Host "Checking Python dependencies..."
& $python -m pip install -r requirements.txt | Out-Host

if (-not (Get-Command pnpm.cmd -ErrorAction SilentlyContinue)) {
    throw "pnpm was not found. Install Node.js and enable pnpm, then run this launcher again."
}

if (-not (Test-Path (Join-Path $webDir "node_modules"))) {
    Write-Host "Installing web dependencies..."
    & pnpm.cmd --dir $webDir install | Out-Host
}

Write-Host "Preparing database..."
& $python -m alembic upgrade head
if (Test-Path (Join-Path $root "data\profile.db")) {
    & $python -m app.migrate_legacy | Out-Host
}

New-Item -ItemType Directory -Force -Path $logDir | Out-Null

if (-not (Test-Url $backendUrl)) {
    Assert-PortAvailable 8000 "API"
    Write-Host "Starting API..."
    Start-Process -FilePath $python -WorkingDirectory $root -WindowStyle Hidden `
        -ArgumentList @("-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000") `
        -RedirectStandardOutput (Join-Path $logDir "api.log") `
        -RedirectStandardError (Join-Path $logDir "api-error.log")
    Wait-ForUrl $backendUrl "API"
}

if (-not (Test-Url $webUrl)) {
    Assert-PortAvailable 5173 "Web"
    Write-Host "Starting web application..."
    $pnpm = (Get-Command pnpm.cmd -ErrorAction Stop).Source
    Start-Process -FilePath $pnpm -WorkingDirectory $root -WindowStyle Hidden `
        -ArgumentList @("--dir", $webDir, "dev", "--host", "127.0.0.1", "--port", "5173", "--strictPort") `
        -RedirectStandardOutput (Join-Path $logDir "web.log") `
        -RedirectStandardError (Join-Path $logDir "web-error.log")
    Wait-ForUrl $webUrl "Web application"
}

Write-Host "Resume Workbench is running at $webUrl"
if (-not $NoBrowser) {
    Start-Process $webUrl
}
