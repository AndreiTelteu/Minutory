[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
# bootstrap.ps1 ends with 'exit'; run it in a child process so a successful
# verification returns control to this script and the GUI actually launches.
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $Root "bootstrap.ps1") -Verify
if ($LASTEXITCODE -ne 0) {
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $Root "bootstrap.ps1")
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
$python = Join-Path $Root ".venv\Scripts\pythonw.exe"

$env:PYTHONDONTWRITEBYTECODE = "1"
$env:MINUTORY_ENV_FILE = Join-Path $Root ".env"
$env:HF_HOME = Join-Path $Root "cache\huggingface"
$env:HF_HUB_CACHE = Join-Path $Root "cache\huggingface\hub"
$env:HF_HUB_OFFLINE = "1"
$env:TRANSFORMERS_OFFLINE = "1"
$env:MINUTORY_MODEL_DIR = Join-Path $Root "models"
$env:MINUTORY_RUNTIME_DIR = Join-Path $Root "libs"
$env:MINUTORY_FFMPEG_PATH = Join-Path $Root "libs\ffmpeg\bin\ffmpeg.exe"
$env:MINUTORY_FFPROBE_PATH = Join-Path $Root "libs\ffmpeg\bin\ffprobe.exe"
$ffmpegBin = Join-Path $Root "libs\ffmpeg\bin"
$env:PATH = "$ffmpegBin;$env:PATH"
$env:MINUTORY_WORK_DIR = Join-Path $Root "work"
$env:MINUTORY_STATE_DB = Join-Path $Root "state\worker.sqlite3"
$env:PYTHONPATH = Join-Path $Root "src"

Start-Process -FilePath $python -ArgumentList "-m", "minutory_worker.gui.app" -WorkingDirectory $Root
