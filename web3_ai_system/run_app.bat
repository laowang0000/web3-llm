@echo off
REM RAG Web3 LLM Application Launcher for Windows Batch

setlocal enabledelayedexpansion

REM Get the directory of this script
set "SCRIPT_DIR=%~dp0"

REM Activate virtual environment
echo Activating virtual environment...
call "%SCRIPT_DIR%.venv\Scripts\activate.bat"

REM Check if OPENAI_API_KEY is set
if not defined OPENAI_API_KEY (
    echo.
    echo WARNING: OPENAI_API_KEY environment variable is not set.
    echo You can set it with: set OPENAI_API_KEY=your_key_here
    echo.
    echo Proceeding anyway - some features may fail without the API key.
    echo.
)

REM Run Streamlit
echo Launching Streamlit application...
python -m streamlit run "%SCRIPT_DIR%app\frontend\streamlit_app.py"

pause
