$ErrorActionPreference = "Stop"

function Resolve-ProjectPython {
    $EnvPython = $env:PYTHON
    if ($EnvPython -and (Test-Path -LiteralPath $EnvPython)) {
        return $EnvPython
    }

    $PythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if ($PythonCommand) {
        return $PythonCommand.Source
    }

    $BundledPython = Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
    if (Test-Path -LiteralPath $BundledPython) {
        return $BundledPython
    }

    throw "No usable Python was found. Install Python 3.12, or set PYTHON to a valid python.exe path."
}

function Test-ProjectVenv {
    param([string]$VenvPython)

    if (-not (Test-Path -LiteralPath $VenvPython)) {
        return $false
    }

    & $VenvPython -c "import sys; print(sys.version)" *> $null
    return ($LASTEXITCODE -eq 0)
}

function Ensure-ProjectVenv {
    param(
        [string]$ProjectRoot,
        [string]$RequirementsPath
    )

    $VenvDir = Join-Path $ProjectRoot ".venv"
    $VenvPython = Join-Path $VenvDir "Scripts\python.exe"

    if (Test-ProjectVenv -VenvPython $VenvPython) {
        Write-Host "[OK] .venv is usable." -ForegroundColor Green
        return $VenvPython
    }

    Write-Host "[WARN] .venv is missing or broken. Rebuilding it now." -ForegroundColor Yellow

    if (Test-Path -LiteralPath $VenvDir) {
        $BackupPath = Join-Path $ProjectRoot (".venv.broken-" + (Get-Date -Format "yyyyMMdd-HHmmss"))
        $ResolvedProject = Resolve-Path -LiteralPath $ProjectRoot
        $ResolvedVenvParent = Split-Path -Parent -Path $VenvDir
        if (-not ((Resolve-Path -LiteralPath $ResolvedVenvParent).Path -eq $ResolvedProject.Path)) {
            throw "Refusing to move .venv because the resolved path is outside the project root."
        }
        Move-Item -LiteralPath $VenvDir -Destination $BackupPath
        Write-Host "[OK] Moved broken .venv to $BackupPath" -ForegroundColor Green
    }

    $BasePython = Resolve-ProjectPython
    Write-Host "[OK] Using Python: $BasePython" -ForegroundColor Green
    & $BasePython -m venv $VenvDir
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to create .venv."
    }

    & $VenvPython -m pip install -r $RequirementsPath
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to install Python requirements."
    }

    Write-Host "[OK] .venv rebuilt successfully." -ForegroundColor Green
    return $VenvPython
}
