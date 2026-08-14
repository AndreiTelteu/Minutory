<#
.SYNOPSIS
    Resolves all runtime assets for Minutory Windows Worker.

.DESCRIPTION
    Downloads upstream assets (Python, FFmpeg, CTranslate2 ROCm wheel),
    builds the wheelhouse and model ZIPs from upstream sources,
    computes archive SHA-256 and installed-tree SHA-256 for each,
    and generates manifests/runtime-assets.local.json.

    Run once on a networked machine. After completion, start.bat will bootstrap
    successfully using the generated local manifest.

.PARAMETER SkipModel
    Skip the ~3 GB faster-whisper-large-v3 model download.

.PARAMETER SkipDiarizationModel
    Skip the gated pyannote speaker-diarization-community-1 model snapshot.

.PARAMETER SkipWheelhouse
    Skip building the runtime wheelhouse (requires pip).

.PARAMETER OnlyFfmpeg
    Resolve and stage only the FFmpeg shared runtime, preserving every other
    entry in an existing local manifest.

.EXAMPLE
    .\resolve-assets.ps1
    .\resolve-assets.ps1 -SkipModel
#>
[CmdletBinding()]
param(
    [switch]$SkipModel,
    [switch]$SkipDiarizationModel,
    [switch]$SkipWheelhouse,
    [switch]$OnlyFfmpeg
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$CacheDir = Join-Path $Root "cache\resolve"
$StagingBase = Join-Path $CacheDir "staging"
$DownloadsDir = Join-Path $Root "cache\downloads"
$AssetMarker = ".minutory-asset.json"
$FfmpegExpectedFiles = @(
    "bin/ffmpeg.exe", "bin/ffprobe.exe",
    "bin/avcodec-61.dll", "bin/avformat-61.dll", "bin/avutil-59.dll",
    "bin/avfilter-10.dll", "bin/swscale-8.dll", "bin/swresample-5.dll"
)

# ---------------------------------------------------------------------------
#  Hash utilities — identical to bootstrap.ps1
# ---------------------------------------------------------------------------

function Get-Sha256Text {
    param([string]$Text)
    $sha = [Security.Cryptography.SHA256]::Create()
    try {
        $bytes = [Text.Encoding]::UTF8.GetBytes($Text)
        return ([BitConverter]::ToString($sha.ComputeHash($bytes))).Replace("-", "").ToLowerInvariant()
    } finally {
        $sha.Dispose()
    }
}

function Get-TreeDigest {
    param([string]$Directory)
    if (-not (Test-Path -LiteralPath $Directory -PathType Container)) { return "" }
    $directoryPrefix = [IO.Path]::GetFullPath($Directory).TrimEnd("\") + "\"
    [string[]]$records = @(Get-ChildItem -LiteralPath $Directory -Recurse -Force -File |
        Where-Object { $_.Name -cne $AssetMarker } |
        ForEach-Object {
            $fullName = [IO.Path]::GetFullPath($_.FullName)
            if (-not $fullName.StartsWith($directoryPrefix, [StringComparison]::OrdinalIgnoreCase)) {
                throw "Installed asset file escapes its managed directory."
            }
            $relative = $fullName.Substring($directoryPrefix.Length).Replace("\", "/")
            $hash = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
            "$relative|$($_.Length)|$hash"
        })
    [Array]::Sort($records, [StringComparer]::Ordinal)
    return (Get-Sha256Text ($records -join "`n"))
}

# ---------------------------------------------------------------------------
#  Download helper
# ---------------------------------------------------------------------------

function Invoke-Download {
    param([string]$Url, [string]$Destination, [string]$Label)
    if (Test-Path -LiteralPath $Destination) {
        Write-Host "  [cached] $Label"
        return
    }
    Write-Host "  Downloading $Label ..."
    $dir = Split-Path -Parent $Destination
    if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Force -Path $dir | Out-Null }
    $partial = "$Destination.partial"
    try {
        $ProgressPreference = "SilentlyContinue"
        Invoke-WebRequest -UseBasicParsing -Uri $Url -OutFile $partial
        Move-Item -LiteralPath $partial -Destination $Destination
    } finally {
        if (Test-Path -LiteralPath $partial) { Remove-Item $partial -Force }
    }
}

# ---------------------------------------------------------------------------
#  ZIP extraction (source_subdir aware, matching bootstrap.ps1)
# ---------------------------------------------------------------------------

function Expand-SourceSubdir {
    param([string]$Archive, [string]$Destination, [string]$SourceSubdir)
    if (Test-Path -LiteralPath $Destination) { Remove-Item $Destination -Recurse -Force }
    New-Item -ItemType Directory -Force -Path $Destination | Out-Null
    $zip = [IO.Compression.ZipFile]::OpenRead($Archive)
    $rootPrefix = if ($SourceSubdir -eq ".") { "" } else { "$SourceSubdir/" }
    $fileCount = 0
    try {
        foreach ($entry in $zip.Entries) {
            $name = $entry.FullName
            if (-not $name.StartsWith($rootPrefix, [StringComparison]::Ordinal)) { continue }
            $relative = $name.Substring($rootPrefix.Length).TrimEnd("/")
            if ([string]::IsNullOrEmpty($relative)) { continue }
            $target = [IO.Path]::GetFullPath((Join-Path $Destination ($relative.Replace("/", "\"))))
            if ($entry.Name.Length -eq 0) {
                New-Item -ItemType Directory -Force -Path $target | Out-Null
            } else {
                New-Item -ItemType Directory -Force -Path (Split-Path -Parent $target) | Out-Null
                $inStream = $entry.Open()
                $outStream = [IO.File]::Open($target, [IO.FileMode]::CreateNew)
                try { $inStream.CopyTo($outStream) } finally { $outStream.Dispose(); $inStream.Dispose() }
                $fileCount++
            }
        }
    } finally {
        $zip.Dispose()
    }
    if ($fileCount -eq 0) {
        throw "No files extracted from '$Archive' under source_subdir '$SourceSubdir'."
    }
    Write-Host "  Extracted $fileCount files"
}

# ---------------------------------------------------------------------------
#  ZIP creation from a directory
# ---------------------------------------------------------------------------

function New-ZipFromDirectory {
    param([string]$SourceDir, [string]$RootName, [string]$Destination)
    if (Test-Path -LiteralPath $Destination) { Remove-Item $Destination -Force }
    $dir = Split-Path -Parent $Destination
    if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Force -Path $dir | Out-Null }
    $zip = [IO.Compression.ZipFile]::Open($Destination, [IO.Compression.ZipArchiveMode]::Create)
    try {
        $prefix = [IO.Path]::GetFullPath($SourceDir).TrimEnd("\") + "\"
        Get-ChildItem -LiteralPath $SourceDir -Recurse -Force -File | ForEach-Object {
            $relative = $_.FullName.Substring($prefix.Length).Replace("\", "/")
            $entryName = "$RootName/$relative"
            $entry = $zip.CreateEntry($entryName, [IO.Compression.CompressionLevel]::Optimal)
            $stream = $entry.Open()
            try {
                $fileStream = [IO.File]::OpenRead($_.FullName)
                try { $fileStream.CopyTo($stream) } finally { $fileStream.Dispose() }
            } finally { $stream.Dispose() }
        }
    } finally {
        $zip.Dispose()
    }
}

# ---------------------------------------------------------------------------
#  Resolve a single downloadable asset
# ---------------------------------------------------------------------------

function Resolve-DownloadAsset {
    param(
        [string]$Id,
        [string]$Url,
        [string]$FileName,
        [string]$SourceSubdir,
        [string[]]$ExpectedFiles
    )
    Write-Host "`n=== $Id ==="
    $archive = Join-Path $CacheDir $FileName
    Invoke-Download $Url $archive "$Id ($FileName)"

    $sha256 = (Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash.ToLowerInvariant()
    Write-Host "  Archive SHA-256: $sha256"

    $staging = Join-Path $StagingBase $Id
    Expand-SourceSubdir $archive $staging $SourceSubdir

    # Verify expected files exist
    foreach ($expected in $ExpectedFiles) {
        $target = Join-Path $staging ($expected.Replace("/", "\"))
        if (-not (Test-Path -LiteralPath $target -PathType Leaf)) {
            throw "Expected file '$expected' not found in extracted $Id."
        }
    }
    Write-Host "  Expected files verified"

    $tree = Get-TreeDigest $staging
    Write-Host "  Tree SHA-256:    $tree"

    return @{
        url                    = $Url
        sha256                 = $sha256
        installed_tree_sha256  = $tree
        source_subdir          = $SourceSubdir
        archive_path           = $archive
    }
}

# ---------------------------------------------------------------------------
#  Build the runtime wheelhouse
# ---------------------------------------------------------------------------

function Build-Wheelhouse {
    Write-Host "`n=== runtime-wheelhouse (building) ==="
    $wheelhouseStaging = Join-Path $StagingBase "wheelhouse-build"
    if (Test-Path $wheelhouseStaging) { Remove-Item $wheelhouseStaging -Recurse -Force }
    New-Item -ItemType Directory -Force -Path $wheelhouseStaging | Out-Null

    # Find pip — prefer pip/pip3, then python -m pip
    # (uv pip does not support the 'download' subcommand)
    $pipMode = $null  # "pip" or "python-m-pip"
    $pipExe = $null
    $pythonExe = $null

    if (Get-Command "pip" -ErrorAction SilentlyContinue) {
        $pipMode = "pip"; $pipExe = "pip"
    } elseif (Get-Command "pip3" -ErrorAction SilentlyContinue) {
        $pipMode = "pip"; $pipExe = "pip3"
    } else {
        $pythonExe = if (Get-Command "python" -ErrorAction SilentlyContinue) { "python" }
                     elseif (Get-Command "python3" -ErrorAction SilentlyContinue) { "python3" }
                     else { $null }
        if ($null -ne $pythonExe) {
            & $pythonExe -m pip --version 2>&1 | Out-Null
            if ($LASTEXITCODE -eq 0) { $pipMode = "python-m-pip" }
        }
    }
    if ($null -eq $pipMode) {
        throw "pip or uv is required to build the wheelhouse. Install pip, uv, or Python, or use -SkipWheelhouse."
    }
    Write-Host "  Using: $(if ($pipMode -eq 'python-m-pip') { "$pythonExe -m pip" } else { $pipExe })"

    $reqFile = Join-Path $Root "requirements-runtime.txt"
    Write-Host "  Downloading wheels for requirements-runtime.txt ..."

    # Download all wheels including transitive dependencies
    if ($pipMode -eq "python-m-pip") {
        & $pythonExe -m pip download `
            -r $reqFile -d $wheelhouseStaging `
            --python-version "3.12" --platform "win_amd64" `
            --implementation "cp" --only-binary ":all:" --no-cache-dir | Out-Host
    } else {
        & $pipExe download `
            -r $reqFile -d $wheelhouseStaging `
            --python-version "3.12" --platform "win_amd64" `
            --implementation "cp" --only-binary ":all:" --no-cache-dir | Out-Host
    }
    if ($LASTEXITCODE -ne 0) {
        throw "Wheel download failed. Ensure pip/uv can download wheels for win_amd64 / cp312."
    }

    # Remove any ctranslate2 wheels (they'll be installed from the ROCm wheel instead)
    $ct2Wheels = Get-ChildItem -LiteralPath $wheelhouseStaging -File |
        Where-Object { $_.Name -match "(?i)^ctranslate2" }
    foreach ($whl in $ct2Wheels) {
        Write-Host "  Removing PyPI ctranslate2 wheel: $($whl.Name)"
        Remove-Item $whl.FullName -Force
    }

    # Copy requirements-runtime.txt into the wheelhouse
    Copy-Item -LiteralPath $reqFile -Destination (Join-Path $wheelhouseStaging "requirements-runtime.txt")

    # Verify expected files
    $expectedWheels = @(
        "requirements-runtime.txt",
        "httpx-0.28.1-py3-none-any.whl",
        "python_dotenv-1.1.1-py3-none-any.whl",
        "tzdata-2025.2-py2.py3-none-any.whl",
        "PySide6-6.9.1-cp39-abi3-win_amd64.whl",
        "faster_whisper-1.2.0-py3-none-any.whl",
        "pyannote_audio-4.0.7-py3-none-any.whl"
    )
    foreach ($expected in $expectedWheels) {
        $target = Join-Path $wheelhouseStaging $expected
        if (-not (Test-Path -LiteralPath $target -PathType Leaf)) {
            throw "Expected wheelhouse file '$expected' not found."
        }
    }
    Write-Host "  Expected files verified"

    $fileCount = (Get-ChildItem -LiteralPath $wheelhouseStaging -File).Count
    Write-Host "  Wheelhouse contains $fileCount files"

    # Create ZIP in bootstrap's download cache so bootstrap skips the download step
    $zipPath = Join-Path $DownloadsDir "runtime-wheelhouse-2026.07.zip"
    Write-Host "  Creating wheelhouse ZIP ..."
    New-ZipFromDirectory $wheelhouseStaging "wheelhouse" $zipPath

    $sha256 = (Get-FileHash -LiteralPath $zipPath -Algorithm SHA256).Hash.ToLowerInvariant()
    Write-Host "  Archive SHA-256: $sha256"

    # Compute tree digest from the staging directory
    $tree = Get-TreeDigest $wheelhouseStaging
    Write-Host "  Tree SHA-256:    $tree"

    return @{
        zipPath                = $zipPath
        sha256                 = $sha256
        installed_tree_sha256  = $tree
        source_subdir          = "wheelhouse"
    }
}

# ---------------------------------------------------------------------------
#  Download and package the faster-whisper-large-v3 model
# ---------------------------------------------------------------------------

function Build-DiarizationModelPackage {
    Write-Host "`n=== pyannote-speaker-diarization-community-1 (building) ==="
    $modelStaging = Join-Path $StagingBase "pyannote-community-1-build"
    if (Test-Path $modelStaging) { Remove-Item $modelStaging -Recurse -Force }
    New-Item -ItemType Directory -Force -Path $modelStaging | Out-Null

    $python = if (Get-Command "python" -ErrorAction SilentlyContinue) { "python" }
              elseif (Get-Command "python3" -ErrorAction SilentlyContinue) { "python3" }
              else { throw "Python with huggingface_hub is required to snapshot the gated pyannote model." }
    $token = $env:MINUTORY_DIARIZATION_TOKEN
    if ([string]::IsNullOrWhiteSpace($token)) {
        throw "Set MINUTORY_DIARIZATION_TOKEN in the environment before resolving the gated pyannote model."
    }
    & $python -c "from huggingface_hub import snapshot_download" 2>$null
    if ($LASTEXITCODE -ne 0) {
        throw "huggingface_hub is required by the asset resolver. Install it into '$python' with: $python -m pip install --upgrade huggingface_hub"
    }
    @"
from huggingface_hub import snapshot_download
snapshot_download(
    repo_id="pyannote/speaker-diarization-community-1",
    local_dir=r"$modelStaging",
    token=r"$token",
)
"@ | & $python -
    if ($LASTEXITCODE -ne 0) { throw "Could not snapshot pyannote/speaker-diarization-community-1." }
    if (-not (Test-Path -LiteralPath (Join-Path $modelStaging "config.yaml") -PathType Leaf)) {
        throw "pyannote snapshot is incomplete: config.yaml is missing."
    }
    # Keep the staged archive name aligned with bootstrap.ps1's deterministic
    # cache convention: <asset-id>-<version>.zip.
    $zipPath = Join-Path $DownloadsDir "pyannote-speaker-diarization-community-1-community-1.zip"
    New-ZipFromDirectory $modelStaging "pyannote-speaker-diarization-community-1" $zipPath
    return @{
        zipPath = $zipPath
        sha256 = (Get-FileHash -LiteralPath $zipPath -Algorithm SHA256).Hash.ToLowerInvariant()
        installed_tree_sha256 = Get-TreeDigest $modelStaging
        source_subdir = "pyannote-speaker-diarization-community-1"
    }
}

function Build-ModelPackage {
    Write-Host "`n=== faster-whisper-large-v3 (building) ==="
    $modelStaging = Join-Path $StagingBase "model-build"
    if (Test-Path $modelStaging) { Remove-Item $modelStaging -Recurse -Force }
    New-Item -ItemType Directory -Force -Path $modelStaging | Out-Null

    $baseUrl = "https://huggingface.co/Systran/faster-whisper-large-v3/resolve/main"
    $modelFiles = @(
        "model.bin",
        "config.json",
        "tokenizer.json",
        "vocabulary.json",
        "preprocessor_config.json"
    )

    foreach ($file in $modelFiles) {
        $dest = Join-Path $modelStaging $file
        Invoke-Download "$baseUrl/$file" $dest $file
    }

    # Verify all files
    foreach ($file in $modelFiles) {
        $target = Join-Path $modelStaging $file
        if (-not (Test-Path -LiteralPath $target -PathType Leaf)) {
            throw "Model file '$file' download failed."
        }
    }
    Write-Host "  All model files downloaded"

    # Create ZIP in bootstrap's download cache so bootstrap skips the download step
    $zipPath = Join-Path $DownloadsDir "faster-whisper-large-v3-large-v3.zip"
    Write-Host "  Creating model ZIP (this may take a while for ~3 GB) ..."
    New-ZipFromDirectory $modelStaging "large-v3" $zipPath

    $sha256 = (Get-FileHash -LiteralPath $zipPath -Algorithm SHA256).Hash.ToLowerInvariant()
    Write-Host "  Archive SHA-256: $sha256"

    $tree = Get-TreeDigest $modelStaging
    Write-Host "  Tree SHA-256:    $tree"

    return @{
        zipPath                = $zipPath
        sha256                 = $sha256
        installed_tree_sha256  = $tree
        source_subdir          = "large-v3"
    }
}

# ---------------------------------------------------------------------------
#  Generate the local manifest
# ---------------------------------------------------------------------------

function Write-LocalManifest {
    param([hashtable]$Results)

    $manifest = [ordered]@{
        schema_version = 2
        generated_for  = "Windows 11 x86-64 / Radeon RX 7900 XTX gfx1100"
        generated_at   = (Get-Date -Format "yyyy-MM-ddTHH:mm:ssK")
        assets         = @()
    }

    # python-runtime
    $py = $Results["python-runtime"]
    $manifest.assets += [ordered]@{
        id                     = "python-runtime"
        version                = "3.12.10"
        url                    = $py["url"]
        sha256                 = $py["sha256"]
        installed_tree_sha256  = $py["installed_tree_sha256"]
        destination            = "libs/python"
        archive                = "zip"
        source_subdir          = $py["source_subdir"]
        expected_files         = @(
            "python.exe", "pythonw.exe",
            "Lib/venv/__init__.py", "Lib/ensurepip/__init__.py"
        )
        distribution_contract  = "full-portable-venv"
        status                 = "resolved"
    }

    # ffmpeg
    $ff = $Results["ffmpeg"]
    $manifest.assets += [ordered]@{
        id                     = "ffmpeg"
        version                = "7.1.1"
        url                    = $ff["url"]
        sha256                 = $ff["sha256"]
        installed_tree_sha256  = $ff["installed_tree_sha256"]
        destination            = "libs/ffmpeg"
        archive                = "zip"
        source_subdir          = $ff["source_subdir"]
        expected_files         = $FfmpegExpectedFiles
        status                 = "resolved"
    }

    # ctranslate2-rocm-wheel
    $ct = $Results["ctranslate2-rocm-wheel"]
    $manifest.assets += [ordered]@{
        id                     = "ctranslate2-rocm-wheel"
        version                = "4.8.1"
        url                    = $ct["url"]
        sha256                 = $ct["sha256"]
        installed_tree_sha256  = $ct["installed_tree_sha256"]
        destination            = "libs/wheels/ctranslate2-rocm-4.8.1"
        archive                = "zip"
        source_subdir          = $ct["source_subdir"]
        expected_files         = @("ctranslate2-4.8.1-cp312-cp312-win_amd64.whl")
        status                 = "resolved"
    }

    # runtime-wheelhouse
    if ($Results.ContainsKey("runtime-wheelhouse")) {
        $wh = $Results["runtime-wheelhouse"]
        # URL is only used if the file doesn't exist in cache/downloads; we pre-stage it there.
        # Use a valid HTTPS placeholder that passes manifest URL validation.
        $whUrl = "https://localhost/.minutory-local-build/runtime-wheelhouse-2026.07.zip"
        $manifest.assets += [ordered]@{
            id                     = "runtime-wheelhouse"
            version                = "2026.07"
            url                    = $whUrl
            sha256                 = $wh["sha256"]
            installed_tree_sha256  = $wh["installed_tree_sha256"]
            destination            = "libs/wheelhouse"
            archive                = "zip"
            source_subdir          = $wh["source_subdir"]
            expected_files         = @(
                "requirements-runtime.txt",
                "httpx-0.28.1-py3-none-any.whl",
                "python_dotenv-1.1.1-py3-none-any.whl",
                "tzdata-2025.2-py2.py3-none-any.whl",
                "PySide6-6.9.1-cp39-abi3-win_amd64.whl",
                "faster_whisper-1.2.0-py3-none-any.whl",
                "pyannote_audio-4.0.7-py3-none-any.whl"
            )
            status                 = "resolved"
        }
    } else {
        $manifest.assets += [ordered]@{
            id                     = "runtime-wheelhouse"
            version                = "2026.07"
            url                    = $null
            sha256                 = $null
            installed_tree_sha256  = $null
            destination            = "libs/wheelhouse"
            archive                = "zip"
            source_subdir          = "wheelhouse"
            expected_files         = @(
                "requirements-runtime.txt",
                "httpx-0.28.1-py3-none-any.whl",
                "python_dotenv-1.1.1-py3-none-any.whl",
                "tzdata-2025.2-py2.py3-none-any.whl",
                "PySide6-6.9.1-cp39-abi3-win_amd64.whl",
                "faster_whisper-1.2.0-py3-none-any.whl",
                "pyannote_audio-4.0.7-py3-none-any.whl"
            )
            status                 = "unresolved"
            notes                  = "Skipped by -SkipWheelhouse."
        }
    }

    # faster-whisper-large-v3
    if ($Results.ContainsKey("faster-whisper-large-v3")) {
        $mdl = $Results["faster-whisper-large-v3"]
        # URL is only used if the file doesn't exist in cache/downloads; we pre-stage it there.
        $mdlUrl = "https://localhost/.minutory-local-build/faster-whisper-large-v3-large-v3.zip"
        $manifest.assets += [ordered]@{
            id                     = "faster-whisper-large-v3"
            version                = "large-v3"
            url                    = $mdlUrl
            sha256                 = $mdl["sha256"]
            installed_tree_sha256  = $mdl["installed_tree_sha256"]
            destination            = "models/large-v3"
            archive                = "zip"
            source_subdir          = $mdl["source_subdir"]
            expected_files         = @(
                "model.bin", "config.json", "tokenizer.json",
                "vocabulary.json", "preprocessor_config.json"
            )
            status                 = "resolved"
        }
    } else {
        $manifest.assets += [ordered]@{
            id                     = "faster-whisper-large-v3"
            version                = "large-v3"
            url                    = $null
            sha256                 = $null
            installed_tree_sha256  = $null
            destination            = "models/large-v3"
            archive                = "zip"
            source_subdir          = "large-v3"
            expected_files         = @(
                "model.bin", "config.json", "tokenizer.json",
                "vocabulary.json", "preprocessor_config.json"
            )
            status                 = "unresolved"
            notes                  = "Skipped by -SkipModel."
        }
    }

    # pyannote speaker-diarization-community-1
    if ($Results.ContainsKey("pyannote-speaker-diarization-community-1")) {
        $diarization = $Results["pyannote-speaker-diarization-community-1"]
        $manifest.assets += [ordered]@{
            id                     = "pyannote-speaker-diarization-community-1"
            version                = "community-1"
            # The archive is pre-staged by this resolver. Bootstrap never receives a Hugging Face token.
            url                    = "https://localhost/.minutory-local-build/pyannote-speaker-diarization-community-1.zip"
            sha256                 = $diarization["sha256"]
            installed_tree_sha256  = $diarization["installed_tree_sha256"]
            destination            = "models/pyannote-speaker-diarization-community-1"
            archive                = "zip"
            source_subdir          = $diarization["source_subdir"]
            expected_files         = @("config.yaml")
            status                 = "resolved"
        }
    } else {
        $manifest.assets += [ordered]@{
            id                     = "pyannote-speaker-diarization-community-1"
            version                = "community-1"
            url                    = $null
            sha256                 = $null
            installed_tree_sha256  = $null
            destination            = "models/pyannote-speaker-diarization-community-1"
            archive                = "zip"
            source_subdir          = "pyannote-speaker-diarization-community-1"
            expected_files         = @("config.yaml")
            status                 = "unresolved"
            notes                  = "Skipped by -SkipDiarizationModel."
        }
    }

    $manifestPath = Join-Path $Root "manifests\runtime-assets.local.json"
    $manifest | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $manifestPath -Encoding UTF8
    Write-Host "`nLocal manifest written: $manifestPath"
    return $manifestPath
}

function Resolve-FfmpegAsset {
    return Resolve-DownloadAsset `
        -Id "ffmpeg" `
        -Url "https://github.com/GyanD/codexffmpeg/releases/download/7.1.1/ffmpeg-7.1.1-full_build-shared.zip" `
        -FileName "ffmpeg-7.1.1-full_build-shared.zip" `
        -SourceSubdir "ffmpeg-7.1.1-full_build-shared" `
        -ExpectedFiles $FfmpegExpectedFiles
}

function Stage-FfmpegBootstrapArchive {
    param([hashtable]$Result)
    $destination = Join-Path $DownloadsDir "ffmpeg-7.1.1.zip"
    Copy-Item -LiteralPath $Result["archive_path"] -Destination $destination -Force
    $actual = (Get-FileHash -LiteralPath $destination -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actual -cne $Result["sha256"]) {
        throw "Staged FFmpeg bootstrap archive failed SHA-256 verification."
    }
    Write-Host "  Bootstrap cache: $destination"
}

function Update-LocalManifestFfmpeg {
    param([hashtable]$Result)
    $manifestPath = Join-Path $Root "manifests\runtime-assets.local.json"
    if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) {
        throw "-OnlyFfmpeg requires an existing resolved local manifest: $manifestPath"
    }
    $manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
    $asset = @($manifest.assets | Where-Object { $_.id -ceq "ffmpeg" })
    if ($asset.Count -ne 1) { throw "Local manifest must contain exactly one FFmpeg asset." }
    $asset[0].version = "7.1.1"
    $asset[0].url = $Result["url"]
    $asset[0].sha256 = $Result["sha256"]
    $asset[0].installed_tree_sha256 = $Result["installed_tree_sha256"]
    $asset[0].destination = "libs/ffmpeg"
    $asset[0].archive = "zip"
    $asset[0].source_subdir = $Result["source_subdir"]
    $asset[0].expected_files = $FfmpegExpectedFiles
    $asset[0].status = "resolved"
    if ($null -ne $manifest.PSObject.Properties["generated_at"]) {
        $manifest.generated_at = Get-Date -Format "yyyy-MM-ddTHH:mm:ssK"
    }
    $manifest | ConvertTo-Json -Depth 10 |
        Set-Content -LiteralPath $manifestPath -Encoding UTF8
    Write-Host "Local manifest updated: $manifestPath"
}

# ===========================================================================
#  MAIN
# ===========================================================================

Write-Host "============================================"
Write-Host " Minutory Windows Worker — Asset Resolver"
Write-Host "============================================"
Write-Host "Root:    $Root"
Write-Host "Cache:   $CacheDir"

New-Item -ItemType Directory -Force -Path $CacheDir | Out-Null
New-Item -ItemType Directory -Force -Path $StagingBase | Out-Null
New-Item -ItemType Directory -Force -Path $DownloadsDir | Out-Null

$results = @{}

if ($OnlyFfmpeg) {
    $results["ffmpeg"] = Resolve-FfmpegAsset
    Stage-FfmpegBootstrapArchive $results["ffmpeg"]
    Update-LocalManifestFfmpeg $results["ffmpeg"]
    Write-Host "FFmpeg shared runtime resolved and staged."
    exit 0
}

# ---- 1. Python 3.12.10 (NuGet portable package) ----
$results["python-runtime"] = Resolve-DownloadAsset `
    -Id "python-runtime" `
    -Url "https://globalcdn.nuget.org/packages/python.3.12.10.nupkg" `
    -FileName "python-3.12.10.nupkg" `
    -SourceSubdir "tools" `
    -ExpectedFiles @("python.exe", "pythonw.exe", "Lib/venv/__init__.py", "Lib/ensurepip/__init__.py")

# ---- 2. FFmpeg 7.1.1 full shared build (required by TorchCodec) ----
$results["ffmpeg"] = Resolve-FfmpegAsset
Stage-FfmpegBootstrapArchive $results["ffmpeg"]

# ---- 3. CTranslate2 ROCm 4.8.1 wheel (GitHub release) ----
$results["ctranslate2-rocm-wheel"] = Resolve-DownloadAsset `
    -Id "ctranslate2-rocm-wheel" `
    -Url "https://github.com/OpenNMT/CTranslate2/releases/download/v4.8.1/rocm-python-wheels-Windows.zip" `
    -FileName "rocm-python-wheels-Windows.zip" `
    -SourceSubdir "temp-windows" `
    -ExpectedFiles @("ctranslate2-4.8.1-cp312-cp312-win_amd64.whl")

# ---- 4. Runtime wheelhouse ----
if (-not $SkipWheelhouse) {
    $results["runtime-wheelhouse"] = Build-Wheelhouse
} else {
    Write-Host "`n=== runtime-wheelhouse === SKIPPED (-SkipWheelhouse)"
}

# ---- 5. Faster-whisper large-v3 model ----
if (-not $SkipModel) {
    $results["faster-whisper-large-v3"] = Build-ModelPackage
} else {
    Write-Host "`n=== faster-whisper-large-v3 === SKIPPED (-SkipModel)"
}

# ---- 6. pyannote speaker diarization model ----
if (-not $SkipDiarizationModel) {
    $results["pyannote-speaker-diarization-community-1"] = Build-DiarizationModelPackage
} else {
    Write-Host "`n=== pyannote-speaker-diarization-community-1 === SKIPPED (-SkipDiarizationModel)"
}

# ---- Generate manifest ----
$manifestPath = Write-LocalManifest $results

# ---- Summary ----
Write-Host "`n============================================"
Write-Host " Summary"
Write-Host "============================================"
foreach ($id in @("python-runtime", "ffmpeg", "ctranslate2-rocm-wheel", "runtime-wheelhouse", "faster-whisper-large-v3", "pyannote-speaker-diarization-community-1")) {
    if ($results.ContainsKey($id)) {
        Write-Host "  [RESOLVED] $id"
    } else {
        Write-Host "  [SKIPPED]  $id"
    }
}
Write-Host ""
Write-Host "Local manifest: $manifestPath"
$unresolved = @(@("python-runtime", "ffmpeg", "ctranslate2-rocm-wheel", "runtime-wheelhouse", "faster-whisper-large-v3", "pyannote-speaker-diarization-community-1") |
    Where-Object { -not $results.ContainsKey($_) })
if ($unresolved.Count -gt 0) {
    Write-Host ""
    Write-Warning "Unresolved assets remain: $($unresolved -join ', '). Bootstrap will fail until all assets are resolved."
} else {
    Write-Host ""
    Write-Host "All assets resolved! Run 'start.bat' to bootstrap." -ForegroundColor Green
}
