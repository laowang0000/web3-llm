# RAG Web3 LLM Application Launcher
# Automatically activates virtual environment and runs Streamlit

$ErrorActionPreference = "Stop"

# Get the directory of this script
$ScriptDir = Split-Path -Parent -Path $MyInvocation.MyCommand.Definition

# Activate virtual environment
Write-Host "Activating virtual environment..." -ForegroundColor Green
& "$ScriptDir\.venv\Scripts\Activate.ps1"

# Check if OPENAI_API_KEY is set
if (-not $env:OPENAI_API_KEY) {
    Write-Host "`nWARNING: OPENAI_API_KEY environment variable is not set." -ForegroundColor Yellow
    Write-Host "You can set it with: `$env:OPENAI_API_KEY='your_key_here'" -ForegroundColor Yellow
    Write-Host "`nProceeding anyway - some features may fail without the API key.`n" -ForegroundColor Yellow
}

# Run Streamlit
Write-Host "Launching Streamlit application..." -ForegroundColor Green
python -m streamlit run "$ScriptDir\app\frontend\streamlit_app.py"
