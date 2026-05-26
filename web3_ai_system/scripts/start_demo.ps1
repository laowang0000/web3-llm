$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent -Path $MyInvocation.MyCommand.Definition
$ProjectRoot = Split-Path -Parent -Path $ScriptDir
$EnvPath = Join-Path $ProjectRoot ".env"
$EnvExamplePath = Join-Path $ProjectRoot ".env.example"
$VenvActivate = Join-Path $ProjectRoot ".venv\Scripts\Activate.ps1"
$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$RequirementsPath = Join-Path $ProjectRoot "requirements.txt"
$EnsureVenvScript = Join-Path $ScriptDir "ensure_venv.ps1"

$ChatModel = "qwen3.6:latest"
$EmbedModel = "nomic-embed-text"
$FastApiUrl = "http://127.0.0.1:8000"
$FastApiDocsUrl = "$FastApiUrl/docs"
$StreamlitUrl = "http://localhost:8501"
$OllamaUrl = "http://localhost:11434"

function Write-Step {
    param([string]$Message)
    Write-Host "`n==> $Message" -ForegroundColor Cyan
}

function Write-Ok {
    param([string]$Message)
    Write-Host "[OK] $Message" -ForegroundColor Green
}

function Write-Warn {
    param([string]$Message)
    Write-Host "[WARN] $Message" -ForegroundColor Yellow
}

function Assert-File {
    param(
        [string]$Path,
        [string]$Message
    )
    if (-not (Test-Path -LiteralPath $Path)) {
        throw $Message
    }
}

function Test-OllamaReachable {
    try {
        Invoke-RestMethod -Uri "$OllamaUrl/api/tags" -Method Get -TimeoutSec 3 | Out-Null
        return $true
    }
    catch {
        return $false
    }
}

function Ensure-OllamaModel {
    param([string]$ModelName)

    Write-Step "Checking Ollama model $ModelName"
    $modelList = & ollama list 2>$null
    if ($LASTEXITCODE -ne 0) {
        throw "Could not list Ollama models. Check that Ollama is installed and reachable."
    }

    if ($modelList -match [regex]::Escape($ModelName)) {
        Write-Ok "Ollama model is available: $ModelName"
        return
    }

    Write-Warn "Model missing. Pulling $ModelName now. This may take a while."
    & ollama pull $ModelName
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to pull Ollama model: $ModelName"
    }
    Write-Ok "Pulled Ollama model: $ModelName"
}

Set-Location -LiteralPath $ProjectRoot
. $EnsureVenvScript
Write-Host "Web3 Finance LLM Backend Functional Test Launcher" -ForegroundColor Green
Write-Host "Project root: $ProjectRoot"

Write-Step "Checking environment file"
if (-not (Test-Path -LiteralPath $EnvPath)) {
    Assert-File -Path $EnvExamplePath -Message ".env is missing and .env.example was not found."
    Copy-Item -LiteralPath $EnvExamplePath -Destination $EnvPath
    Write-Ok "Created .env from .env.example"
}
else {
    Write-Ok ".env exists"
}

Write-Step "Checking Python virtual environment"
$VenvPython = Ensure-ProjectVenv -ProjectRoot $ProjectRoot -RequirementsPath $RequirementsPath
Assert-File -Path $VenvActivate -Message ".venv activation script was not found after rebuild."
. $VenvActivate
Write-Ok "Activated .venv"

Write-Step "Checking Python packages"
Assert-File -Path $RequirementsPath -Message "requirements.txt was not found."
& $VenvPython -m pip check | Out-Host
if ($LASTEXITCODE -ne 0) {
    Write-Warn "pip check reported dependency issues. Installing requirements."
    & $VenvPython -m pip install -r $RequirementsPath
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to install Python requirements."
    }
}

$ImportCheck = @"
import importlib.util
missing = []
modules = ["fastapi", "streamlit", "httpx", "pandas", "chromadb", "xgboost", "dotenv", "langchain"]
for module in modules:
    if importlib.util.find_spec(module) is None:
        missing.append(module)
if missing:
    raise SystemExit("Missing required Python modules: " + ", ".join(missing))
print("Required Python imports are available.")
"@
& $VenvPython -c $ImportCheck
if ($LASTEXITCODE -ne 0) {
    Write-Warn "Some required modules are missing. Installing requirements."
    & $VenvPython -m pip install -r $RequirementsPath
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to install Python requirements."
    }
}
Write-Ok "Python package check completed"

Write-Step "Checking Ollama"
$OllamaCommand = Get-Command ollama -ErrorAction SilentlyContinue
if (-not $OllamaCommand) {
    throw "Ollama is not installed or not in PATH. Install Ollama first, then rerun this script."
}
Write-Ok "Ollama command found"

if (-not (Test-OllamaReachable)) {
    Write-Warn "Ollama service is not reachable. Starting ollama serve in the background."
    Start-Process -FilePath "ollama" -ArgumentList "serve" -WindowStyle Hidden
    Start-Sleep -Seconds 5
}

if (-not (Test-OllamaReachable)) {
    throw "Ollama did not become reachable at $OllamaUrl. Start it manually with: ollama serve"
}
Write-Ok "Ollama service is reachable"

Ensure-OllamaModel -ModelName $ChatModel
Ensure-OllamaModel -ModelName $EmbedModel

Write-Step "Indexing local RAG sources"
& $VenvPython -m app.scripts.index_rag
if ($LASTEXITCODE -ne 0) {
    throw "RAG indexing failed. Check Ollama embedding model and local documents."
}
Write-Ok "RAG indexing completed"

Write-Step "Starting FastAPI backend in a new PowerShell window"
$BackendCommand = "& { Set-Location -LiteralPath '$ProjectRoot'; . '$VenvActivate'; python -m uvicorn app.api.main:app --reload --host 127.0.0.1 --port 8000 }"
Start-Process -FilePath "powershell.exe" -ArgumentList "-NoExit", "-ExecutionPolicy", "Bypass", "-Command", $BackendCommand
Write-Ok "FastAPI starting at $FastApiUrl"

Write-Step "Starting Streamlit functional test console in a new PowerShell window"
$StreamlitCommand = "& { Set-Location -LiteralPath '$ProjectRoot'; . '$VenvActivate'; python run_streamlit.py }"
Start-Process -FilePath "powershell.exe" -ArgumentList "-NoExit", "-ExecutionPolicy", "Bypass", "-Command", $StreamlitCommand
Write-Ok "Streamlit functional test console starting at $StreamlitUrl"

Write-Host "`nFunctional test URLs" -ForegroundColor Green
Write-Host "FastAPI docs: $FastApiDocsUrl"
Write-Host "Streamlit:    $StreamlitUrl"
Write-Host "`nUse start_final_ui.bat for the polished React presentation UI." -ForegroundColor Yellow
Write-Host "`nTo stop the demo, run:" -ForegroundColor Yellow
Write-Host ".\scripts\stop_demo.ps1"
