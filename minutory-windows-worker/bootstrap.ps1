[CmdletBinding()]
param(
    [switch]$DryRun,
    [switch]$Verify,
    [string]$ManifestPath = ""
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
if ([string]::IsNullOrWhiteSpace($ManifestPath)) {
    $localManifest = Join-Path $Root "manifests\runtime-assets.local.json"
    $ManifestPath = if (Test-Path -LiteralPath $localManifest) {
        $localManifest
    } else {
        Join-Path $Root "manifests\runtime-assets.json"
    }
}

function Read-AssetManifest {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "Runtime manifest not found: $Path"
    }
    $document = Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json
    if ($document.schema_version -ne 1 -or $null -eq $document.assets) {
        throw "Runtime manifest schema_version must be 1 and assets must be present."
    }
    $required = @(
        "python-runtime", "ffmpeg", "ctranslate2-rocm-wheel",
        "runtime-wheelhouse", "faster-whisper-large-v3"
    )
    $seen = @{}
    foreach ($asset in $document.assets) {
        if ([string]::IsNullOrWhiteSpace($asset.id) `
                -or $asset.id -cnotmatch "^[A-Za-z0-9][A-Za-z0-9._-]*$" `
                -or $seen.ContainsKey($asset.id)) {
            throw "Runtime manifest contains a missing or duplicate asset ID."
        }
        $seen[$asset.id] = $true
        if ($asset.status -ne "resolved" -or [string]::IsNullOrWhiteSpace($asset.url) `
                -or [string]::IsNullOrWhiteSpace($asset.sha256)) {
            throw "Asset '$($asset.id)' is unresolved. Bootstrap fails closed until its exact HTTPS URL and SHA-256 are verified."
        }
        $uri = [Uri]$asset.url
        if ($uri.Scheme -ne "https") {
            throw "Asset '$($asset.id)' must use HTTPS."
        }
        if ($asset.sha256 -cnotmatch "^[0-9a-f]{64}$") {
            throw "Asset '$($asset.id)' must use a lowercase SHA-256."
        }
        if ([string]::IsNullOrWhiteSpace($asset.version) `
                -or $asset.version -cnotmatch "^[A-Za-z0-9][A-Za-z0-9._-]*$") {
            throw "Asset '$($asset.id)' has an unsafe version value."
        }
        if ($asset.archive -notin @("zip", "file")) {
            throw "Asset '$($asset.id)' has an unsupported archive type."
        }
        $parts = $asset.destination.Replace("\", "/").Split("/")
        if ($parts[0] -notin @("libs", "models", "cache") -or $parts -contains "..") {
            throw "Asset '$($asset.id)' destination escapes managed directories."
        }
    }
    foreach ($id in $required) {
        if (-not $seen.ContainsKey($id)) {
            throw "Runtime manifest is missing '$id'."
        }
    }
    return $document
}

function Install-Asset {
    param([object]$Asset)
    $destination = Join-Path $Root $Asset.destination
    if (Test-Path -LiteralPath $destination) {
        if ($Asset.archive -eq "file") {
            $installedHash = (Get-FileHash -LiteralPath $destination -Algorithm SHA256).Hash.ToLowerInvariant()
        } else {
            $marker = Join-Path $destination ".minutory-asset.sha256"
            $installedHash = if (Test-Path -LiteralPath $marker) {
                (Get-Content -LiteralPath $marker -Raw).Trim()
            } else {
                ""
            }
        }
        if ($installedHash -ceq $Asset.sha256) {
            Write-Host "Already verified: $($Asset.id)"
            return
        }
        throw "Managed destination for '$($Asset.id)' exists without its verified hash. Move it aside and re-run bootstrap."
    }
    $downloadDir = Join-Path $Root "cache\downloads"
    New-Item -ItemType Directory -Force -Path $downloadDir | Out-Null
    $downloadExtension = if ($Asset.archive -eq "zip") { ".zip" } else { ".bin" }
    $download = Join-Path $downloadDir "$($Asset.id)-$($Asset.version)$downloadExtension"
    if (-not (Test-Path -LiteralPath $download)) {
        Invoke-WebRequest -UseBasicParsing -Uri ([Uri]$Asset.url) -OutFile $download
    }
    $actual = (Get-FileHash -LiteralPath $download -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actual -cne $Asset.sha256) {
        Remove-Item -LiteralPath $download -Force
        throw "SHA-256 mismatch for '$($Asset.id)'. Download was removed."
    }
    if ($Asset.archive -eq "file") {
        $parent = Split-Path -Parent $destination
        New-Item -ItemType Directory -Force -Path $parent | Out-Null
        $temporary = "$destination.installing"
        Copy-Item -LiteralPath $download -Destination $temporary -Force
        Move-Item -LiteralPath $temporary -Destination $destination -Force
        return
    }
    $temporaryDir = "$destination.installing-$([Guid]::NewGuid().ToString('N'))"
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $destination) | Out-Null
    New-Item -ItemType Directory -Force -Path $temporaryDir | Out-Null
    try {
        Expand-Archive -LiteralPath $download -DestinationPath $temporaryDir -Force
        Set-Content -LiteralPath (Join-Path $temporaryDir ".minutory-asset.sha256") `
            -Value $Asset.sha256 -NoNewline
        Move-Item -LiteralPath $temporaryDir -Destination $destination
    } finally {
        if (Test-Path -LiteralPath $temporaryDir) {
            Remove-Item -LiteralPath $temporaryDir -Recurse -Force
        }
    }
}

try {
    $manifest = Read-AssetManifest -Path $ManifestPath
    Write-Host "Manifest verified: $ManifestPath"
    foreach ($asset in $manifest.assets) {
        Write-Host ("{0,-28} {1,-12} -> {2}" -f $asset.id, $asset.version, $asset.destination)
    }
    if ($DryRun) {
        Write-Host "Dry run complete. No downloads or filesystem changes were performed."
        exit 0
    }
    if ($Verify) {
        foreach ($asset in $manifest.assets) {
            $destination = Join-Path $Root $asset.destination
            if (-not (Test-Path -LiteralPath $destination)) {
                throw "Managed asset '$($asset.id)' is missing at $destination."
            }
            $installedHash = if ($asset.archive -eq "file") {
                (Get-FileHash -LiteralPath $destination -Algorithm SHA256).Hash.ToLowerInvariant()
            } else {
                $marker = Join-Path $destination ".minutory-asset.sha256"
                if (Test-Path -LiteralPath $marker) {
                    (Get-Content -LiteralPath $marker -Raw).Trim()
                } else {
                    ""
                }
            }
            if ($installedHash -cne $asset.sha256) {
                throw "Managed asset '$($asset.id)' does not match the manifest."
            }
        }
    } else {
        foreach ($asset in $manifest.assets) {
            Install-Asset -Asset $asset
        }
    }
    $python = Join-Path $Root "libs\python\python.exe"
    if (-not (Test-Path -LiteralPath $python)) {
        throw "Managed Python is missing at $python."
    }
    if (-not $Verify -and -not (Test-Path -LiteralPath (Join-Path $Root ".venv\Scripts\python.exe"))) {
        & $python -m venv (Join-Path $Root ".venv")
    }
    $venvPython = Join-Path $Root ".venv\Scripts\python.exe"
    if (-not (Test-Path -LiteralPath $venvPython)) {
        throw "Managed virtual environment is missing. Run bootstrap without -Verify."
    }
    if (-not $Verify) {
        $wheelhouse = Join-Path $Root "libs\wheelhouse"
        $rocmWheel = Join-Path $Root "libs\wheels\ctranslate2_rocm-4.8.1-cp312-cp312-win_amd64.whl"
        $forbidden = Get-ChildItem -LiteralPath $wheelhouse -File |
            Where-Object { $_.Name -match "(?i)^ctranslate2" }
        if ($null -ne $forbidden) {
            throw "The runtime wheelhouse contains CTranslate2. Remove it; only the official ROCm wheel is allowed."
        }
        & $venvPython -m pip install --disable-pip-version-check --no-index $rocmWheel
        if ($LASTEXITCODE -ne 0) { throw "Official CTranslate2 ROCm wheel installation failed." }
        & $venvPython -m pip install --disable-pip-version-check --no-index `
            --find-links $wheelhouse -r (Join-Path $Root "requirements-runtime.txt")
        if ($LASTEXITCODE -ne 0) { throw "Offline runtime dependency installation failed." }
    }
    $env:PYTHONPATH = Join-Path $Root "src"
    & $venvPython -m minutory_worker.runtime_verify
    if ($LASTEXITCODE -ne 0) { throw "Runtime verification failed. Review the actionable errors above." }
    Write-Host "Minutory Worker runtime is ready."
} catch {
    Write-Error $_.Exception.Message
    exit 1
}
