[CmdletBinding()]
param(
    [switch]$DryRun,
    [switch]$Verify,
    [string]$ManifestPath = ""
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem

$BootstrapSchema = "minutory-bootstrap-v2"
$AssetMarker = ".minutory-asset.json"
$ReadyMarker = ".minutory-ready.json"
$RuntimeVerificationMarker = ".minutory-runtime-verified.json"
$RuntimeVerificationSchema = "minutory-runtime-verification-v1"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$env:PYTHONDONTWRITEBYTECODE = "1"
$env:PIP_DISABLE_PIP_VERSION_CHECK = "1"
$env:PIP_NO_CACHE_DIR = "1"
if ([string]::IsNullOrWhiteSpace($ManifestPath)) {
    $localManifest = Join-Path $Root "manifests\runtime-assets.local.json"
    $ManifestPath = if (Test-Path -LiteralPath $localManifest) {
        $localManifest
    } else {
        Join-Path $Root "manifests\runtime-assets.json"
    }
}

$Contracts = @{
    "python-runtime" = @("libs/python", "zip")
    "ffmpeg" = @("libs/ffmpeg", "zip")
    "ctranslate2-rocm-wheel" = @(
        "libs/wheels/ctranslate2-rocm-4.8.1", "zip"
    )
    "runtime-wheelhouse" = @("libs/wheelhouse", "zip")
    "faster-whisper-large-v3" = @("models/large-v3", "zip")
    "pyannote-speaker-diarization-community-1" = @("models/pyannote-speaker-diarization-community-1", "zip")
}
$RequiredExpectedFiles = @{
    "python-runtime" = @("python.exe", "pythonw.exe", "Lib/venv/__init__.py", "Lib/ensurepip/__init__.py")
    "ffmpeg" = @("bin/ffmpeg.exe", "bin/ffprobe.exe")
    "ctranslate2-rocm-wheel" = @("ctranslate2-4.8.1-cp312-cp312-win_amd64.whl")
    "runtime-wheelhouse" = @(
        "requirements-runtime.txt", "httpx-0.28.1-py3-none-any.whl",
        "python_dotenv-1.1.1-py3-none-any.whl", "tzdata-2025.2-py2.py3-none-any.whl",
        "PySide6-6.9.1-cp39-abi3-win_amd64.whl", "faster_whisper-1.2.0-py3-none-any.whl",
        "pyannote_audio-4.0.7-py3-none-any.whl"
    )
    "faster-whisper-large-v3" = @(
        "model.bin", "config.json", "tokenizer.json", "vocabulary.json", "preprocessor_config.json"
    )
    "pyannote-speaker-diarization-community-1" = @(
        "config.yaml"
    )
}

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

function Get-ReadinessFingerprint {
    $manifestHash = (Get-FileHash -LiteralPath $ManifestPath -Algorithm SHA256).Hash.ToLowerInvariant()
    $requirementsHash = (
        Get-FileHash -LiteralPath (Join-Path $Root "requirements-runtime.txt") -Algorithm SHA256
    ).Hash.ToLowerInvariant()
    return (Get-Sha256Text "$BootstrapSchema|$manifestHash|$requirementsHash")
}

function Get-RuntimeVerificationFingerprint {
    param([string]$Venv)
    $readyMarker = Join-Path $Venv $ReadyMarker
    $python = Join-Path $Venv "Scripts\python.exe"
    $ctranslate2Package = Join-Path $Venv "Lib\site-packages\ctranslate2\__init__.py"
    $ctranslate2Native = Join-Path $Venv "Lib\site-packages\ctranslate2\ctranslate2.dll"
    foreach ($path in @($readyMarker, $python, $ctranslate2Package)) {
        if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
            throw "Runtime verification input is missing: $path"
        }
    }
    $readyHash = (Get-FileHash -LiteralPath $readyMarker -Algorithm SHA256).Hash.ToLowerInvariant()
    $pythonHash = (Get-FileHash -LiteralPath $python -Algorithm SHA256).Hash.ToLowerInvariant()
    $ctranslate2PackageHash = (Get-FileHash -LiteralPath $ctranslate2Package -Algorithm SHA256).Hash.ToLowerInvariant()
    $ctranslate2NativeHash = if (Test-Path -LiteralPath $ctranslate2Native -PathType Leaf) {
        (Get-FileHash -LiteralPath $ctranslate2Native -Algorithm SHA256).Hash.ToLowerInvariant()
    } else {
        "missing"
    }
    return (Get-Sha256Text `
        "$RuntimeVerificationSchema|$readyHash|$pythonHash|$ctranslate2PackageHash|$ctranslate2NativeHash")
}

function Test-RuntimeVerifiedToday {
    param([string]$Venv, [string]$Fingerprint)
    $marker = Join-Path $Venv $RuntimeVerificationMarker
    if (-not (Test-Path -LiteralPath $marker -PathType Leaf)) { return $false }
    try {
        $document = Get-Content -LiteralPath $marker -Raw | ConvertFrom-Json
        return $document.schema -ceq $RuntimeVerificationSchema `
            -and $document.date -ceq (Get-Date -Format "yyyy-MM-dd") `
            -and $document.fingerprint -ceq $Fingerprint
    } catch {
        return $false
    }
}

function Write-RuntimeVerificationMarker {
    param([string]$Venv, [string]$Fingerprint)
    @{
        schema = $RuntimeVerificationSchema
        date = Get-Date -Format "yyyy-MM-dd"
        fingerprint = $Fingerprint
    } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $Venv $RuntimeVerificationMarker) -Encoding UTF8
}

function Assert-SafeRelativePath {
    param([string]$Value, [string]$Label, [switch]$AllowDot)
    if ([string]::IsNullOrWhiteSpace($Value) -or $Value.Contains("\") `
            -or $Value.StartsWith("/") -or $Value -match "^[A-Za-z]:" `
            -or $Value.Split("/") -contains ".." `
            -or (-not $AllowDot -and $Value -eq ".")) {
        throw "$Label must be a safe POSIX relative path."
    }
}

function Read-AssetManifest {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "Runtime manifest not found: $Path"
    }
    $document = Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json
    if ($document.schema_version -ne 2 -or $null -eq $document.assets) {
        throw "Runtime manifest schema_version must be 2 and assets must be present."
    }
    $seen = @{}
    $unresolved = @()
    foreach ($asset in $document.assets) {
        $assetId = [string]$asset.id
        if (-not $Contracts.ContainsKey($assetId) -or $seen.ContainsKey($assetId)) {
            throw "Runtime manifest contains an unknown or duplicate asset ID."
        }
        $seen[$assetId] = $true
        $contract = $Contracts[$assetId]
        if ($asset.destination -cne $contract[0] -or $asset.archive -cne $contract[1]) {
            throw "Asset '$($asset.id)' violates its exact destination/archive contract."
        }
        if ($asset.archive -eq "zip") {
            Assert-SafeRelativePath ([string]$asset.source_subdir) "source_subdir" -AllowDot
        } elseif ($null -ne $asset.source_subdir) {
            throw "File asset '$($asset.id)' source_subdir must be null."
        }
        if ($null -eq $asset.expected_files -or $asset.expected_files.Count -eq 0) {
            throw "Asset '$($asset.id)' must declare expected_files."
        }
        $expectedSeen = @{}
        foreach ($expected in $asset.expected_files) {
            Assert-SafeRelativePath ([string]$expected) "expected file"
            $key = ([string]$expected).ToLowerInvariant()
            if ($expectedSeen.ContainsKey($key)) { throw "Asset '$($asset.id)' has duplicate expected files." }
            $expectedSeen[$key] = $true
        }
        foreach ($requiredFile in $RequiredExpectedFiles[$assetId]) {
            if (-not $expectedSeen.ContainsKey($requiredFile.ToLowerInvariant())) {
                throw "Asset '$($asset.id)' omits required expected file '$requiredFile'."
            }
        }
        if ($asset.id -eq "python-runtime" `
                -and $asset.distribution_contract -cne "full-portable-venv") {
            throw "Managed Python must be a full portable distribution with venv and ensurepip; the embeddable ZIP is unsupported."
        }
        if ([string]::IsNullOrWhiteSpace($asset.version) `
                -or $asset.version -cnotmatch "^[A-Za-z0-9][A-Za-z0-9._-]*$") {
            throw "Asset '$($asset.id)' has an unsafe version."
        }
        if ($asset.status -eq "unresolved") {
            if ($null -ne $asset.url -or $null -ne $asset.sha256 `
                    -or $null -ne $asset.installed_tree_sha256) {
                throw "Unresolved asset '$($asset.id)' must have null URL and hashes."
            }
            $unresolved += $asset.id
            continue
        }
        if ($asset.status -ne "resolved" -or [string]::IsNullOrWhiteSpace($asset.url) `
                -or [string]::IsNullOrWhiteSpace($asset.sha256)) {
            throw "Asset '$($asset.id)' is not resolved."
        }
        $assetUri = [Uri]$asset.url
        if ($assetUri.Scheme -cne "https" -or [string]::IsNullOrWhiteSpace($assetUri.Host) `
                -or -not [string]::IsNullOrEmpty($assetUri.UserInfo)) {
            throw "Asset '$($asset.id)' must use credential-free HTTPS."
        }
        if ($asset.sha256 -cnotmatch "^[0-9a-f]{64}$") {
            throw "Asset '$($asset.id)' must use a lowercase SHA-256."
        }
        if ($asset.archive -eq "zip" `
                -and $asset.installed_tree_sha256 -cnotmatch "^[0-9a-f]{64}$") {
            throw "Asset '$($asset.id)' must use a lowercase installed-tree SHA-256."
        }
        if ($asset.archive -eq "file" -and $null -ne $asset.installed_tree_sha256) {
            throw "File asset '$($asset.id)' installed-tree SHA-256 must be null."
        }
    }
    foreach ($id in $Contracts.Keys) {
        if (-not $seen.ContainsKey($id)) { throw "Runtime manifest is missing '$id'." }
    }
    if ($unresolved.Count -gt 0) {
        throw "Runtime assets are unresolved; bootstrap fails closed: $($unresolved -join ', ')."
    }
    return $document
}

function Clear-ManagedPythonBytecode {
    # Any python run without PYTHONDONTWRITEBYTECODE (ad-hoc tooling, test
    # venvs based on the managed runtime) writes __pycache__ into libs\python
    # and breaks the installed-tree verification. Bytecode is regenerable, so
    # drop it before hashing instead of failing closed.
    $managed = Join-Path $Root "libs\python"
    if (-not (Test-Path -LiteralPath $managed -PathType Container)) { return }
    Get-ChildItem -LiteralPath $managed -Recurse -Force -Directory -Filter "__pycache__" |
        Remove-Item -Recurse -Force
    Get-ChildItem -LiteralPath $managed -Recurse -Force -File -Filter "*.pyc" |
        Remove-Item -Force
}

function Get-TreeDigest {
    param([string]$Directory)
    if (-not (Test-Path -LiteralPath $Directory -PathType Container)) { return "" }
    $directoryPrefix = [IO.Path]::GetFullPath($Directory).TrimEnd("\") + "\"
    $markerPath = [IO.Path]::GetFullPath((Join-Path $Directory $AssetMarker))
    Assert-NoReparsePoints $Directory
    [string[]]$records = @(Get-ChildItem -LiteralPath $Directory -Recurse -Force -File |
        Where-Object { [IO.Path]::GetFullPath($_.FullName) -cne $markerPath } |
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

function Assert-NoReparsePoints {
    param([string]$Directory)
    $reparse = Get-ChildItem -LiteralPath $Directory -Recurse -Force |
        Where-Object { ($_.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0 } |
        Select-Object -First 1
    if ($null -ne $reparse) {
        throw "Installed asset contains unsupported reparse point '$($reparse.FullName)'."
    }
}

function Get-AssetFileSnapshot {
    param([string]$Directory)
    if (-not (Test-Path -LiteralPath $Directory -PathType Container)) { return @{} }
    $directoryPrefix = [IO.Path]::GetFullPath($Directory).TrimEnd("\") + "\"
    $markerPath = [IO.Path]::GetFullPath((Join-Path $Directory $AssetMarker))
    Assert-NoReparsePoints $Directory
    $files = @{}
    Get-ChildItem -LiteralPath $Directory -Recurse -Force -File |
        Where-Object { [IO.Path]::GetFullPath($_.FullName) -cne $markerPath } |
        ForEach-Object {
            $fullName = [IO.Path]::GetFullPath($_.FullName)
            if (-not $fullName.StartsWith($directoryPrefix, [StringComparison]::OrdinalIgnoreCase)) {
                throw "Installed asset file escapes its managed directory."
            }
            $relative = $fullName.Substring($directoryPrefix.Length).Replace("\", "/")
            $files[$relative] = @{
                bytes = [Int64]$_.Length
                last_write_utc_ticks = $_.LastWriteTimeUtc.Ticks
            }
        }
    return $files
}

function Test-AssetFileSnapshot {
    param([object]$Snapshot, [string]$Directory)
    if ($null -eq $Snapshot) { return $false }
    $current = Get-AssetFileSnapshot $Directory
    $cachedNames = @($Snapshot.PSObject.Properties.Name)
    if ($cachedNames.Count -ne $current.Count) { return $false }
    foreach ($name in $cachedNames) {
        if (-not $current.ContainsKey($name)) { return $false }
        $cached = $Snapshot.$name
        if ($null -eq $cached) { return $false }
        $bytes = $cached.PSObject.Properties["bytes"]
        $ticks = $cached.PSObject.Properties["last_write_utc_ticks"]
        if ($null -eq $bytes -or $null -eq $ticks) { return $false }
        if ([Int64]$bytes.Value -ne [Int64]$current[$name].bytes `
                -or [Int64]$ticks.Value -ne [Int64]$current[$name].last_write_utc_ticks) {
            return $false
        }
    }
    return $true
}

function Write-AssetMarker {
    param([string]$Destination, [object]$Asset, [string]$Tree)
    @{
        schema = 2
        archive_sha256 = $Asset.sha256
        tree_sha256 = $Tree
        files = Get-AssetFileSnapshot $Destination
    } | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $Destination $AssetMarker) -Encoding UTF8
}

function Assert-ExpectedFiles {
    param([object]$Asset, [string]$Destination)
    foreach ($expected in $Asset.expected_files) {
        $target = if ($Asset.archive -eq "file") { $Destination } else {
            Join-Path $Destination ([string]$expected).Replace("/", "\")
        }
        if (-not (Test-Path -LiteralPath $target -PathType Leaf)) {
            throw "Asset '$($Asset.id)' is missing expected file '$expected'."
        }
    }
}

function Test-InstalledAsset {
    param([object]$Asset)
    $destination = Join-Path $Root $Asset.destination
    if ($Asset.archive -eq "file") {
        if (-not (Test-Path -LiteralPath $destination -PathType Leaf)) { return $false }
        return (Get-FileHash -LiteralPath $destination -Algorithm SHA256).Hash.ToLowerInvariant() `
            -ceq $Asset.sha256
    }
    if (-not (Test-Path -LiteralPath $destination -PathType Container)) { return $false }
    try {
        Assert-ExpectedFiles $Asset $destination
        $markerPath = Join-Path $destination $AssetMarker
        if (-not (Test-Path -LiteralPath $markerPath -PathType Leaf)) { return $false }
        $marker = Get-Content -LiteralPath $markerPath -Raw | ConvertFrom-Json
        if ($marker.archive_sha256 -cne $Asset.sha256 `
                -or $marker.tree_sha256 -cne $Asset.installed_tree_sha256) {
            return $false
        }
        $schemaProperty = $marker.PSObject.Properties["schema"]
        $filesProperty = $marker.PSObject.Properties["files"]
        if ($null -ne $schemaProperty -and $schemaProperty.Value -eq 2 `
                -and $null -ne $filesProperty -and (Test-AssetFileSnapshot $filesProperty.Value $destination)) {
            return $true
        }
        # Existing v1 markers get a complete SHA-256 validation exactly once;
        # subsequent launches use this path/size/mtime snapshot and avoid
        # rereading the multi-gigabyte model.
        Write-AssetMarker $destination $Asset $tree
        return $true
    } catch {
        return $false
    }
}

function Expand-SafeZip {
    param([string]$Archive, [string]$Destination, [string]$SourceSubdir)
    $zip = [IO.Compression.ZipFile]::OpenRead($Archive)
    $targets = @{}
    $rootPrefix = if ($SourceSubdir -eq ".") { "" } else { "$SourceSubdir/" }
    try {
        foreach ($entry in $zip.Entries) {
            $name = $entry.FullName
            if ($name.Contains("\") -or $name.StartsWith("/") -or $name -match "^[A-Za-z]:" `
                    -or $name.Split("/") -contains "..") {
                throw "ZIP contains unsafe path '$name'."
            }
            $unixType = ($entry.ExternalAttributes -shr 16) -band 0xF000
            $windowsAttrs = $entry.ExternalAttributes -band 0xFFFF
            if ($unixType -eq 0xA000 -or ($windowsAttrs -band 0x400) -ne 0) {
                throw "ZIP contains a symlink or reparse entry '$name'."
            }
            if (-not $name.StartsWith($rootPrefix, [StringComparison]::Ordinal)) { continue }
            $relative = $name.Substring($rootPrefix.Length).TrimEnd("/")
            if ([string]::IsNullOrEmpty($relative)) { continue }
            Assert-SafeRelativePath $relative "ZIP target"
            $key = $relative.ToLowerInvariant()
            if ($targets.ContainsKey($key)) { throw "ZIP contains duplicate target '$relative'." }
            foreach ($parent in $targets.Keys) {
                if ($key.StartsWith("$parent/") -and -not $targets[$parent]) {
                    throw "ZIP contains file/directory collision '$relative'."
                }
                if ($parent.StartsWith("$key/") -and $entry.Name.Length -gt 0) {
                    throw "ZIP contains file/directory collision '$relative'."
                }
            }
            $isDirectory = $entry.Name.Length -eq 0
            $targets[$key] = $isDirectory
            $target = [IO.Path]::GetFullPath((Join-Path $Destination $relative.Replace("/", "\")))
            $prefix = [IO.Path]::GetFullPath($Destination) + [IO.Path]::DirectorySeparatorChar
            if (-not $target.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase)) {
                throw "ZIP target escapes staging directory."
            }
            if ($isDirectory) {
                New-Item -ItemType Directory -Force -Path $target | Out-Null
            } else {
                New-Item -ItemType Directory -Force -Path (Split-Path -Parent $target) | Out-Null
                $input = $entry.Open()
                $output = [IO.File]::Open($target, [IO.FileMode]::CreateNew)
                try { $input.CopyTo($output) } finally { $output.Dispose(); $input.Dispose() }
            }
        }
    } finally {
        $zip.Dispose()
    }
    if (($targets.Values | Where-Object { -not $_ }).Count -eq 0) {
        throw "ZIP source_subdir '$SourceSubdir' contains no files."
    }
}

function Move-Atomically {
    param([string]$Staging, [string]$Destination)
    $backup = "$Destination.previous-$([Guid]::NewGuid().ToString('N'))"
    $hadPrevious = Test-Path -LiteralPath $Destination
    try {
        if ($hadPrevious) { Move-Item -LiteralPath $Destination -Destination $backup }
        Move-Item -LiteralPath $Staging -Destination $Destination
        if ($hadPrevious) { Remove-Item -LiteralPath $backup -Recurse -Force }
    } catch {
        if (-not (Test-Path -LiteralPath $Destination) -and (Test-Path -LiteralPath $backup)) {
            Move-Item -LiteralPath $backup -Destination $Destination
        }
        throw
    }
}

function Install-Asset {
    param([object]$Asset)
    if (Test-InstalledAsset $Asset) {
        Write-Host "Already verified: $($Asset.id)"
        return
    }
    $downloadDir = Join-Path $Root "cache\downloads"
    New-Item -ItemType Directory -Force -Path $downloadDir | Out-Null
    $extension = if ($Asset.archive -eq "zip") { ".zip" } else { ".bin" }
    $download = Join-Path $downloadDir "$($Asset.id)-$($Asset.version)$extension"
    if (-not (Test-Path -LiteralPath $download)) {
        $partial = "$download.partial-$([Guid]::NewGuid().ToString('N'))"
        try {
            Invoke-WebRequest -UseBasicParsing -Uri ([Uri]$Asset.url) -OutFile $partial
            $partialHash = (Get-FileHash -LiteralPath $partial -Algorithm SHA256).Hash.ToLowerInvariant()
            if ($partialHash -cne $Asset.sha256) {
                throw "SHA-256 mismatch for '$($Asset.id)'."
            }
            Move-Item -LiteralPath $partial -Destination $download
        } finally {
            if (Test-Path -LiteralPath $partial) { Remove-Item -LiteralPath $partial -Force }
        }
    }
    $actual = (Get-FileHash -LiteralPath $download -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actual -cne $Asset.sha256) {
        Remove-Item -LiteralPath $download -Force
        throw "SHA-256 mismatch for '$($Asset.id)'; the download was removed."
    }
    $destination = Join-Path $Root $Asset.destination
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $destination) | Out-Null
    if ($Asset.archive -eq "file") {
        $stagingFile = "$destination.installing-$([Guid]::NewGuid().ToString('N'))"
        try {
            Copy-Item -LiteralPath $download -Destination $stagingFile
            if ((Get-FileHash $stagingFile -Algorithm SHA256).Hash.ToLowerInvariant() -cne $Asset.sha256) {
                throw "Staged file verification failed for '$($Asset.id)'."
            }
            Move-Atomically $stagingFile $destination
        } finally {
            if (Test-Path -LiteralPath $stagingFile) { Remove-Item $stagingFile -Force }
        }
        return
    }
    $staging = "$destination.installing-$([Guid]::NewGuid().ToString('N'))"
    New-Item -ItemType Directory -Path $staging | Out-Null
    try {
        Expand-SafeZip $download $staging ([string]$Asset.source_subdir)
        Assert-ExpectedFiles $Asset $staging
        if ($Asset.id -eq "runtime-wheelhouse") {
            if (Get-ChildItem -LiteralPath $staging -File | Where-Object Name -Match "(?i)^ctranslate2") {
                throw "The staged wheelhouse contains CTranslate2; only the official ROCm wheel is allowed."
            }
            $stagedRequirements = Join-Path $staging "requirements-runtime.txt"
            $trackedRequirements = Join-Path $Root "requirements-runtime.txt"
            if ((Get-FileHash $stagedRequirements -Algorithm SHA256).Hash `
                    -cne (Get-FileHash $trackedRequirements -Algorithm SHA256).Hash) {
                throw "The staged wheelhouse requirements file does not match the tracked runtime requirements."
            }
        }
        $tree = Get-TreeDigest $staging
        if ($tree -cne $Asset.installed_tree_sha256) {
            throw "Installed-tree SHA-256 mismatch for '$($Asset.id)'."
        }
        Write-AssetMarker $staging $Asset $tree
        Move-Atomically $staging $destination
    } finally {
        if (Test-Path -LiteralPath $staging) { Remove-Item $staging -Recurse -Force }
    }
}

function Assert-PythonContract {
    $python = Join-Path $Root "libs\python\python.exe"
    & $python -m venv --help | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Managed Python cannot create venvs; embeddable Python is unsupported." }
    & $python -m ensurepip --version | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Managed Python has no ensurepip; use a full portable distribution." }
}

function Assert-VenvReady {
    param([string]$Venv)
    $python = Join-Path $Venv "Scripts\python.exe"
    $pythonw = Join-Path $Venv "Scripts\pythonw.exe"
    if (-not (Test-Path $python) -or -not (Test-Path $pythonw)) { throw "Managed venv is incomplete." }
    & $python -m pip check
    if ($LASTEXITCODE -ne 0) { throw "Managed venv dependency verification failed." }
    $env:PYTHONPATH = Join-Path $Root "src"
    $env:HF_HUB_OFFLINE = "1"
    $env:TRANSFORMERS_OFFLINE = "1"
    & $python -m minutory_worker.runtime_verify
    if ($LASTEXITCODE -ne 0) { throw "Runtime verification failed. Review the actionable errors above." }
}

try {
    Clear-ManagedPythonBytecode
    $manifest = Read-AssetManifest $ManifestPath
    Write-Host "Manifest schema and exact layout verified: $ManifestPath"
    foreach ($asset in $manifest.assets) {
        Write-Host ("{0,-28} {1,-12} -> {2}" -f $asset.id, $asset.version, $asset.destination)
    }
    if ($DryRun) {
        Write-Host "Dry run complete. No downloads or filesystem changes were performed."
        exit 0
    }
    if ($Verify) {
        foreach ($asset in $manifest.assets) {
            if (-not (Test-InstalledAsset $asset)) {
                throw "Managed asset '$($asset.id)' failed expected-file or installed-tree verification."
            }
        }
        Assert-PythonContract
        $venv = Join-Path $Root ".venv"
        $marker = Join-Path $venv $ReadyMarker
        if (-not (Test-Path -LiteralPath $marker -PathType Leaf)) {
            throw "Managed venv readiness marker is missing."
        }
        $ready = Get-Content -LiteralPath $marker -Raw | ConvertFrom-Json
        if ($ready.schema -cne $BootstrapSchema `
                -or $ready.fingerprint -cne (Get-ReadinessFingerprint)) {
            throw "Managed venv readiness marker is stale."
        }
        $runtimeFingerprint = Get-RuntimeVerificationFingerprint $venv
        if (Test-RuntimeVerifiedToday $venv $runtimeFingerprint) {
            Write-Host "Daily runtime verification is already current."
        } else {
            Assert-VenvReady $venv
            Write-RuntimeVerificationMarker $venv $runtimeFingerprint
            Write-Host "Daily runtime verification completed."
        }
        Write-Host "Minutory Worker runtime is verified and ready."
        exit 0
    }

    foreach ($asset in $manifest.assets) { Install-Asset $asset }
    Assert-PythonContract
    $wheelhouse = Join-Path $Root "libs\wheelhouse"
    if (Get-ChildItem -LiteralPath $wheelhouse -File | Where-Object Name -Match "(?i)^ctranslate2") {
        throw "The wheelhouse contains CTranslate2; only the official ROCm wheel is allowed."
    }
    $managedPython = Join-Path $Root "libs\python\python.exe"
    $venv = Join-Path $Root ".venv"
    $stagingVenv = Join-Path $Root ".venv.installing-$([Guid]::NewGuid().ToString('N'))"
    try {
        & $managedPython -m venv $stagingVenv
        if ($LASTEXITCODE -ne 0) { throw "Staged virtual environment creation failed." }
        $venvPython = Join-Path $stagingVenv "Scripts\python.exe"
        $rocmWheel = Join-Path $Root `
            "$($Contracts['ctranslate2-rocm-wheel'][0])\ctranslate2-4.8.1-cp312-cp312-win_amd64.whl"
        & $venvPython -m pip install --disable-pip-version-check --no-index `
            --find-links $wheelhouse $rocmWheel
        if ($LASTEXITCODE -ne 0) { throw "Official CTranslate2 ROCm wheel installation failed." }
        & $venvPython -m pip install --disable-pip-version-check --no-index `
            --find-links $wheelhouse -r (Join-Path $Root "requirements-runtime.txt")
        if ($LASTEXITCODE -ne 0) { throw "Offline runtime dependency installation failed." }
        $siteCt2 = Join-Path $stagingVenv "Lib\site-packages\ctranslate2"
        if (Test-Path -LiteralPath $siteCt2) {
            # CTranslate2 4.8.1 Windows ROCm wheel imports amdhip64_7.dll and
            # hipblas.dll: it requires ROCm 7 user-mode libraries (e.g. the
            # LM Studio win-llama-rocm-vendor-v6 backend). ROCm 6 libraries
            # (amdhip64_6.dll) are incompatible and cause cuBLAS failures.
            $rocmCandidateDirs = @(
                "C:\Users\Andrei\.lmstudio\extensions\backends\vendor\win-llama-rocm-vendor-v6\bin",
                "C:\Users\Andrei\.lmstudio\extensions\backends\vendor\win-llama-rocm-vendor-v5\bin",
                "$env:HIP_PATH\bin",
                "C:\Program Files\AMD\ROCm\bin"
            )
            foreach ($dir in $rocmCandidateDirs) {
                if (Test-Path -LiteralPath $dir) {
                    Get-ChildItem -LiteralPath $dir | ForEach-Object {
                        $dest = Join-Path $siteCt2 $_.Name
                        if (-not (Test-Path -LiteralPath $dest)) {
                            Copy-Item -LiteralPath $_.FullName -Destination $dest -Recurse -Force
                        }
                    }
                    break
                }
            }
            $libHipblas = Join-Path $siteCt2 "libhipblas.dll"
            $hipblasAlias = Join-Path $siteCt2 "hipblas.dll"
            if ((Test-Path -LiteralPath $libHipblas) -and -not (Test-Path -LiteralPath $hipblasAlias)) {
                Copy-Item -LiteralPath $libHipblas -Destination $hipblasAlias -Force
            }
            $sys32Hip = "C:\Windows\System32\amdhip64_7.dll"
            if (-not (Test-Path -LiteralPath $sys32Hip)) { $sys32Hip = "C:\Windows\System32\amdhip64_6.dll" }
            if (Test-Path -LiteralPath $sys32Hip) {
                $targetHip = Join-Path $siteCt2 (Split-Path -Leaf $sys32Hip)
                if (-not (Test-Path -LiteralPath $targetHip)) {
                    Copy-Item -LiteralPath $sys32Hip -Destination $targetHip -Force
                }
            }
        }
        Assert-VenvReady $stagingVenv
        @{
            schema = $BootstrapSchema
            fingerprint = (Get-ReadinessFingerprint)
        } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $stagingVenv $ReadyMarker) -Encoding UTF8
        $runtimeFingerprint = Get-RuntimeVerificationFingerprint $stagingVenv
        Write-RuntimeVerificationMarker $stagingVenv $runtimeFingerprint
        Move-Atomically $stagingVenv $venv
    } finally {
        if (Test-Path -LiteralPath $stagingVenv) {
            Remove-Item -LiteralPath $stagingVenv -Recurse -Force
        }
    }
    Write-Host "Minutory Worker runtime is ready."
} catch {
    Write-Error "$($_.Exception.Message)`n$($_.ScriptStackTrace)"
    exit 1
}
