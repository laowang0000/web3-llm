$ErrorActionPreference = "Stop"

Write-Host "Stopping Web3 Finance LLM demo processes..." -ForegroundColor Cyan

$Targets = @(
    @{
        NamePattern = "python|uvicorn"
        CommandPattern = "uvicorn app.api.main:app"
        Label = "FastAPI / uvicorn"
    },
    @{
        NamePattern = "python|streamlit"
        CommandPattern = "run_streamlit.py|streamlit run"
        Label = "Streamlit"
    }
)

$StoppedAny = $false

foreach ($Target in $Targets) {
    $Processes = Get-CimInstance Win32_Process |
        Where-Object {
            $_.Name -match $Target.NamePattern -and
            $_.CommandLine -match $Target.CommandPattern
        }

    if (-not $Processes) {
        Write-Host "[OK] No running $($Target.Label) process found." -ForegroundColor Green
        continue
    }

    foreach ($Process in $Processes) {
        Write-Host "Stopping $($Target.Label) process PID $($Process.ProcessId)" -ForegroundColor Yellow
        Stop-Process -Id $Process.ProcessId -Force
        $StoppedAny = $true
    }
}

if ($StoppedAny) {
    Write-Host "Demo processes stopped." -ForegroundColor Green
}
else {
    Write-Host "Nothing needed to be stopped." -ForegroundColor Green
}

Write-Host "Ollama was left running because it may be used by other local projects." -ForegroundColor Yellow
