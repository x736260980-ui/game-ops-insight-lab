param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$GitArgs
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$rootForBash = $root.Replace([char]92, [char]47)
$gitCommand = Get-Command git -ErrorAction Stop
$gitRoot = Split-Path -Parent (Split-Path -Parent $gitCommand.Source)
$bash = Join-Path $gitRoot "bin\bash.exe"

if (-not (Test-Path -LiteralPath $bash)) {
    throw "Git for Windows 缺少 bash.exe：$bash"
}

# Codex Desktop 等嵌入式进程可能不把 Git 自带的 /usr/bin 与
# git-core 放进非交互 shell 的 PATH，导致 git submodule 找不到
# basename、sed 和 git-sh-setup。通过 Git Bash 显式补齐，不修改系统 Git。
function ConvertTo-BashLiteral {
    param([string]$Value)
    $singleQuote = [string]([char]39)
    $replacement = $singleQuote + '"' + $singleQuote + '"' + $singleQuote
    return $singleQuote + $Value.Replace($singleQuote, $replacement) + $singleQuote
}

$quotedArgs = ($GitArgs | ForEach-Object { ConvertTo-BashLiteral $_ }) -join " "
$command = "export PATH=/usr/bin:/mingw64/bin:/mingw64/libexec/git-core:`$PATH; git -C $(ConvertTo-BashLiteral $rootForBash) $quotedArgs"
& $bash -lc $command
exit $LASTEXITCODE
