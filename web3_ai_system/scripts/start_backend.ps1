param(
    [int]$Port = 8000
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent -Path $MyInvocation.MyCommand.Definition
$ProjectRoot = Split-Path -Parent -Path $ScriptDir
$RequirementsPath = Join-Path $ProjectRoot "requirements.txt"
$EnsureVenvScript = Join-Path $ScriptDir "ensure_venv.ps1"
$FastApiUrl = "http://127.0.0.1:$Port"

function Get-PortOwners {
    param([int]$Port)

    try {
        $connections = Get-NetTCPConnection -LocalAddress 127.0.0.1 -LocalPort $Port -ErrorAction SilentlyContinue
    }
    catch {
        $connections = @()
    }

    $owners = @()
    foreach ($connection in $connections) {
        $process = Get-Process -Id $connection.OwningProcess -ErrorAction SilentlyContinue
        $owners += [pscustomobject]@{
            Pid = $connection.OwningProcess
            ProcessName = if ($process) { $process.ProcessName } else { "unknown" }
            State = $connection.State
        }
    }

    return $owners | Sort-Object Pid -Unique
}

function Assert-PortAvailable {
    param([int]$Port)

    $owners = @(Get-PortOwners -Port $Port)
    if (-not $owners) {
        return
    }

    Write-Host "[ERROR] Port $Port is already in use." -ForegroundColor Red
    foreach ($owner in $owners) {
        Write-Host "        PID $($owner.Pid) ($($owner.ProcessName)) - $($owner.State)" -ForegroundColor Yellow
    }

    Write-Host ""
    Write-Host "Try one of these:" -ForegroundColor Yellow
    Write-Host "  .\scripts\stop_demo.ps1"
    Write-Host "  .\scripts\start_backend.ps1 -Port 8001"
    throw "FastAPI could not start because 127.0.0.1:$Port is already occupied."
}

. $EnsureVenvScript

Set-Location -LiteralPath $ProjectRoot
Write-Host "Starting Web3 Finance LLM FastAPI backend" -ForegroundColor Green
Write-Host "Project root: $ProjectRoot"

$VenvPython = Ensure-ProjectVenv -ProjectRoot $ProjectRoot -RequirementsPath $RequirementsPath

Assert-PortAvailable -Port $Port
Write-Host "[OK] FastAPI docs will be available at $FastApiUrl/docs" -ForegroundColor Green
& $VenvPython -m uvicorn app.api.main:app --host 127.0.0.1 --port $Port
