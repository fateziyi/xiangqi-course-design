param([int]$FrontendPort = 5173, [int]$GamePort = 8765, [int]$AIPort = 8766)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$pythonExe = Join-Path $projectRoot '.venv\Scripts\python.exe'
$viteEntry = Join-Path $projectRoot 'frontend\node_modules\vite\bin\vite.js'
$nodeExe = (Get-Command node.exe -ErrorAction Stop).Source
if (-not (Test-Path -LiteralPath $pythonExe) -or -not (Test-Path -LiteralPath $viteEntry)) { throw '依赖未安装，请先运行 scripts\setup.ps1。' }
& $pythonExe -c 'import sys,websockets; assert sys.version_info[:2]==(3,12); assert websockets.__version__==''15.0.1'''
if ($LASTEXITCODE -ne 0) { throw 'Python 环境不匹配，请重新运行 setup.ps1。' }
if (@($FrontendPort,$GamePort,$AIPort | Select-Object -Unique).Count -ne 3) { throw '三个端口不能重复。' }
foreach ($port in @($FrontendPort,$GamePort,$AIPort)) {
    if ($port -lt 1024 -or $port -gt 65535) { throw "无效端口 $port" }
    $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback,$port)
    try { $listener.Start() } catch { throw "端口 $port 已占用；请关闭已有项目服务或更换端口。" } finally { $listener.Stop() }
}
$runtimeDir = Join-Path $projectRoot '.runtime'
New-Item -ItemType Directory -Path $runtimeDir -Force | Out-Null
$processes = @()
. (Join-Path $PSScriptRoot 'windows-job.ps1')
$processJob = [XiangqiProcessJob]::new()
$oldAI = $env:XIANGQI_AI_PORT; $oldGame = $env:XIANGQI_GAME_PORT; $oldURL = $env:XIANGQI_AI_URL; $oldFrontURL = $env:VITE_GAME_URL
try {
    $env:XIANGQI_AI_PORT = "$AIPort"; $env:XIANGQI_GAME_PORT = "$GamePort"
    $env:XIANGQI_AI_URL = "ws://127.0.0.1:$AIPort"; $env:VITE_GAME_URL = "ws://127.0.0.1:$GamePort"
    $processes += $processJob.Start($pythonExe, '-m ai.server', $projectRoot, (Join-Path $runtimeDir 'ai.log'), (Join-Path $runtimeDir 'ai-error.log'))
    $processes += $processJob.Start($pythonExe, '-m backend.server', $projectRoot, (Join-Path $runtimeDir 'game.log'), (Join-Path $runtimeDir 'game-error.log'))
    $viteArguments = '"' + $viteEntry + '" --host 127.0.0.1 --port ' + $FrontendPort + ' --strictPort'
    $processes += $processJob.Start($nodeExe, $viteArguments, (Join-Path $projectRoot 'frontend'), (Join-Path $runtimeDir 'frontend.log'), (Join-Path $runtimeDir 'frontend-error.log'))
    Write-Host "正在启动 http://127.0.0.1:$FrontendPort 。此终端保持运行，Ctrl+C 停止本次创建的服务。"
    while ($true) {
        foreach ($process in $processes) { if ($process.HasExited) { throw "服务退出，请查看 $runtimeDir 日志。" } }
        Start-Sleep -Milliseconds 500
    }
} finally {
    $processJob.Dispose()
    $env:XIANGQI_AI_PORT=$oldAI; $env:XIANGQI_GAME_PORT=$oldGame; $env:XIANGQI_AI_URL=$oldURL; $env:VITE_GAME_URL=$oldFrontURL
}
