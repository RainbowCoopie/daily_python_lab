# 注册 Windows 计划任务: 每天定时跑 run_daily.ps1
param(
    [string]$Time = '09:30',
    [string]$TaskName = 'DailyPythonLab'
)

$runner = Join-Path $PSScriptRoot 'run_daily.ps1'
if (-not (Test-Path $runner)) { throw "找不到 $runner" }

$exists = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($exists) {
    Write-Host "任务已存在, 先移除: $TaskName"
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}

$action = New-ScheduledTaskAction `
    -Execute 'powershell.exe' `
    -Argument ('-NoProfile -ExecutionPolicy Bypass -File "{0}"' -f $runner) `
    -WorkingDirectory (Split-Path -Parent $PSScriptRoot)

$trigger = New-ScheduledTaskTrigger -Daily -At $Time
$settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -DontStopIfGoingOnBatteries `
    -AllowStartIfOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 30)

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Description '每天生成一个测试全绿的 Python 小工程并推送到 GitHub' | Out-Null

$info = Get-ScheduledTask -TaskName $TaskName
$next = (Get-ScheduledTaskInfo -TaskName $TaskName).NextRunTime
Write-Host ("已注册: {0}  触发时间: 每天 {1}  下次运行: {2}" -f $info.TaskName, $Time, $next)
