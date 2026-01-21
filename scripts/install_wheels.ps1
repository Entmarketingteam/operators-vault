# Download wheels from PyPI via Invoke-WebRequest (avoids pip HTTP/2 issues) and install.
# Run from project root: .\scripts\install_wheels.ps1
# Requires: psycopg2-binary already installed (or add it to PACKAGES).

$ErrorActionPreference = "Stop"
$Python = "python"
$PACKAGES = @(
    "python-dotenv",
    "httpx", "httpcore", "certifi", "anyio", "sniffio", "idna", "h11",
    "anthropic", "pydantic", "typing_extensions",
    "deepgram-sdk", "websockets",
    "meilisearch",
    "yt-dlp",
    "openai", "distro",
    "fastapi", "starlette", "uvicorn"
)

$wheelsDir = Join-Path (Join-Path $PSScriptRoot "..") "wheels"
New-Item -ItemType Directory -Force -Path $wheelsDir | Out-Null

function Get-WheelUrl {
    param([string]$Package)
    $j = Invoke-RestMethod "https://pypi.org/pypi/$Package/json" -UseBasicParsing
    $v = $j.info.version
    $wheels = $j.urls | Where-Object { $_.packagetype -eq "bdist_wheel" }
    # Prefer: py3-none-any (pure), or cp312 win_amd64
    $u = $wheels | Where-Object { $_.filename -match "py3-none-any" } | Select-Object -First 1
    if (-not $u) { $u = $wheels | Where-Object { $_.filename -match "cp312.*win_amd64" } | Select-Object -First 1 }
    if (-not $u) { $u = $wheels | Select-Object -First 1 }
    if ($u) { return @($u.url, $u.filename) }
    return @($null, $null)
}

foreach ($pkg in $PACKAGES) {
    $pkg = $pkg.Trim()
    if (-not $pkg) { continue }
    Write-Host "Fetching $pkg ..."
    try {
        $r = Get-WheelUrl -Package $pkg
        $url, $fname = $r[0], $r[1]
        if (-not $url) { Write-Warning "  No wheel for $pkg, skipping."; continue }
        $path = Join-Path $wheelsDir $fname
        if (-not (Test-Path $path)) {
            Invoke-WebRequest -Uri $url -OutFile $path -UseBasicParsing
        }
        & $Python -m pip install --no-deps $path 2>&1 | Out-Null
        if ($LASTEXITCODE -eq 0) { Write-Host "  Installed $pkg" } else { Write-Warning "  pip install failed for $pkg" }
    } catch {
        Write-Warning "  Error: $pkg -- $_"
    }
}

Write-Host "Done. Run: pip install -r requirements.txt to fill any remaining deps (may hit HTTP/2)."
