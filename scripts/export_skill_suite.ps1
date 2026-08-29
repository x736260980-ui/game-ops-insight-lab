$ErrorActionPreference = "Stop"
$OutputEncoding = [Console]::OutputEncoding = [Text.UTF8Encoding]::new()
$root = Split-Path -Parent $PSScriptRoot
$skill = Join-Path $root ".agents\skills\game-ops-insight-suite"
$outputDir = Join-Path $root "dist-skills"
$archive = Join-Path $outputDir "game-ops-insight-suite.zip"

if (-not (Test-Path -LiteralPath (Join-Path $skill "SKILL.md"))) {
    throw "找不到一体化 Skill：$skill"
}

New-Item -ItemType Directory -Path $outputDir -Force | Out-Null
if (Test-Path -LiteralPath $archive) {
    Remove-Item -LiteralPath $archive -Force
}

Compress-Archive -LiteralPath $skill -DestinationPath $archive -CompressionLevel Optimal
Write-Host "Skill Suite 已导出：$archive" -ForegroundColor Green

