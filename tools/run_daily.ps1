# 定时任务入口: 跑一次完整流水线, 日志落到 logs/
# 默认不调用任何本地模型（不占显卡）；需要时手动加 -WithLLM
param(
    [switch]$NoPush,
    [switch]$WithLLM
)

$ErrorActionPreference = 'Continue'
$root = Split-Path -Parent $PSScriptRoot
$py = Join-Path $root '.venv\Scripts\python.exe'
if (-not (Test-Path $py)) { $py = 'python' }

$logDir = Join-Path $root 'logs'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$log = Join-Path $logDir "run_$stamp.log"

$env:PYTHONIOENCODING = 'utf-8'
$cliArgs = @('-m', 'lab', 'run')
if ($NoPush) { $cliArgs += '--no-push' }
if ($WithLLM) { $cliArgs += '--llm' }

Push-Location $root
try {
    & $py @cliArgs 2>&1 | Tee-Object -FilePath $log
    $code = $LASTEXITCODE
} finally {
    Pop-Location
}

Add-Content -Path $log -Value ("exit_code={0} finished_at={1}" -f $code, (Get-Date -Format 's'))

# 只留 30 天日志
Get-ChildItem $logDir -Filter 'run_*.log' -ErrorAction SilentlyContinue |
    Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-30) } |
    Remove-Item -Force -ErrorAction SilentlyContinue

exit $code
