@echo off
setlocal
cd /d "%~dp0"

echo Web3 Finance LLM RAG Index Preparation
echo Backend root: %CD%
echo.

if not exist ".venv\Scripts\python.exe" (
    echo ERROR: .venv Python was not found.
    echo Run start_final_ui.bat once so the environment can be created.
    exit /b 1
)

".venv\Scripts\python.exe" -m app.scripts.check_rag_index
if not errorlevel 1 (
    echo.
    echo Existing RAG index found. Nothing to rebuild.
    echo Delete storage\chroma_insight only if you intentionally want a full rebuild.
    exit /b 0
)

".venv\Scripts\python.exe" -m app.scripts.index_rag
if errorlevel 1 (
    echo.
    echo ERROR: RAG indexing failed.
    echo Keep Ollama running, close heavy apps, then rerun prepare_rag_index.bat.
    exit /b 1
)

echo.
echo RAG index is ready. Future launcher runs will skip the slow indexing step.
exit /b 0
