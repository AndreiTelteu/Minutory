[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = Join-Path $Root ".venv\Scripts\pythonw.exe"

if (-not (Test-Path -LiteralPath $python)) {
    & (Join-Path $Root "bootstrap.ps1")
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

$env:MINUTORY_ENV_FILE = Join-Path $Root ".env"
$env:HF_HOME = Join-Path $Root "cache\huggingface"
$env:HF_HUB_CACHE = Join-Path $Root "cache\huggingface\hub"
$env:MINUTORY_MODEL_DIR = Join-Path $Root "models"
$env:MINUTORY_RUNTIME_DIR = Join-Path $Root "libs"
$env:MINUTORY_FFMPEG_PATH = Join-Path $Root "libs\ffmpeg\bin\ffmpeg.exe"
$env:MINUTORY_FFPROBE_PATH = Join-Path $Root "libs\ffmpeg\bin\ffprobe.exe"
$env:MINUTORY_WORK_DIR = Join-Path $Root "work"
$env:MINUTORY_STATE_DB = Join-Path $Root "state\worker.sqlite3"
$env:PYTHONPATH = Join-Path $Root "src"

Start-Process -FilePath $python -ArgumentList "-m", "minutory_worker.gui.app" -WorkingDirectory $Root
