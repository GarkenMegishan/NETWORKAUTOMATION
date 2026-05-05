# package-skill.ps1
# Bundles network-automation/ into network-automation.skill (a renamed zip),
# matching the structure the official package_skill.py would have produced.
#
# Run from PowerShell:  .\package-skill.ps1
# Or double-click:      package-skill.bat (which calls this with the right exec policy)

$ErrorActionPreference = "Stop"

# Resolve paths relative to where this script lives
$here    = Split-Path -Parent $MyInvocation.MyCommand.Path
$skill   = Join-Path $here "network-automation"
$out     = Join-Path $here "network-automation.skill"

# Mirror package_skill.py's exclusion list
$excludeDirs  = @("evals", "__pycache__", "node_modules")
$excludeFiles = @(".DS_Store", "*.pyc")

# Sanity checks
if (-not (Test-Path $skill)) {
    Write-Host "ERROR: skill folder not found at $skill" -ForegroundColor Red
    exit 1
}
if (-not (Test-Path (Join-Path $skill "SKILL.md"))) {
    Write-Host "ERROR: SKILL.md not found in $skill" -ForegroundColor Red
    exit 1
}

# Stage a clean copy in TEMP without the excluded items
$staging = Join-Path $env:TEMP "skill-stage-$(Get-Random)"
$staged  = Join-Path $staging "network-automation"

Write-Host "Staging clean copy in $staging..."
$null = robocopy $skill $staged /E /XD $excludeDirs /XF $excludeFiles /NFL /NDL /NJH /NJS /NP

# robocopy returns 0-7 for success, 8+ for errors
if ($LASTEXITCODE -ge 8) {
    Write-Host "ERROR: robocopy failed (exit $LASTEXITCODE)" -ForegroundColor Red
    Remove-Item $staging -Recurse -Force -ErrorAction SilentlyContinue
    exit 1
}

# Remove old skill file if present
if (Test-Path $out) {
    Write-Host "Removing existing $out"
    Remove-Item $out
}

# Use .NET's ZipFile API directly so we can force forward-slash paths.
# Compress-Archive on Windows writes backslash separators, which violate the
# zip spec and cause "invalid characters" errors in stricter installers.
Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem

Write-Host "Compressing..."
$archive = [System.IO.Compression.ZipFile]::Open($out, [System.IO.Compression.ZipArchiveMode]::Create)
try {
    Get-ChildItem $staged -Recurse -File | ForEach-Object {
        # Path relative to the staging root, with forward slashes
        $rel = $_.FullName.Substring($staging.Length + 1) -replace '\\', '/'
        [System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile(
            $archive, $_.FullName, $rel,
            [System.IO.Compression.CompressionLevel]::Optimal
        ) | Out-Null
    }
} finally {
    $archive.Dispose()
}

# Cleanup
Remove-Item $staging -Recurse -Force

# Report
$size = (Get-Item $out).Length
Write-Host ""
Write-Host "Done." -ForegroundColor Green
Write-Host "  Created: $out"
Write-Host "  Size:    $([math]::Round($size/1KB, 1)) KB"
Write-Host ""
Write-Host "Install this file in Cowork via Settings -> Skills, or wherever your"
Write-Host "skill installer lives."
