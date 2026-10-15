param([string]$Python = "")
$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
Push-Location -LiteralPath $projectRoot
try {
    $venvPath = Join-Path $projectRoot '.venv'
    $venvPython = Join-Path $venvPath 'Scripts\python.exe'
    $usable = $false
    if (Test-Path -LiteralPath $venvPython) {
        try {
            & $venvPython -c 'import sys; assert sys.version_info[:2] == (3,12) and sys.version_info.releaselevel == ''final''' 2>$null
            $usable = $LASTEXITCODE -eq 0
        } catch { $usable = $false }
    }
    if (-not $usable) {
        if (-not $Python) {
            $bundledPython = Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
            if (Test-Path -LiteralPath $bundledPython) { $Python = $bundledPython }
            else { throw '请使用 -Python 指定 Python 3.12 稳定版的 python.exe 绝对路径。' }
        }
        & $Python -c 'import sys; assert sys.version_info[:2] == (3,12) and sys.version_info.releaselevel == ''final'', ''Requires stable Python 3.12'''
        if ($LASTEXITCODE -ne 0) { throw 'Python 运行时不符合要求' }
        if (Test-Path -LiteralPath $venvPath) {
            $backupPath = Join-Path $projectRoot ('.venv.backup-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '-' + [guid]::NewGuid().ToString('N').Substring(0,8))
            # Rename only this project's environment, retaining all its contents.
            if ([IO.Path]::GetDirectoryName([IO.Path]::GetFullPath($venvPath)) -ne $projectRoot -or [IO.Path]::GetDirectoryName([IO.Path]::GetFullPath($backupPath)) -ne $projectRoot) { throw '虚拟环境路径不在项目根目录内。' }
            Move-Item -LiteralPath $venvPath -Destination $backupPath
            Write-Host "已保留失效虚拟环境：$backupPath"
        }
        & $Python -m venv .venv
        if ($LASTEXITCODE -ne 0) { throw '创建虚拟环境失败' }
    }
    & .\.venv\Scripts\python.exe -c 'import sys; assert sys.version_info[:2] == (3,12) and sys.version_info.releaselevel == ''final'', ''Requires stable Python 3.12'''
    if ($LASTEXITCODE -ne 0) { throw '已有虚拟环境不符合 Python 3.12 稳定版要求，请选择新的环境目录。' }
    & .\.venv\Scripts\python.exe -m pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) { throw '安装 Python 依赖失败' }
    Push-Location -LiteralPath (Join-Path $projectRoot 'frontend')
    try { & npm.cmd ci; if ($LASTEXITCODE -ne 0) { throw '安装前端依赖失败' } }
    finally { Pop-Location }
    Write-Host '依赖安装完成。运行 .\scripts\start.ps1 启动。'
} finally { Pop-Location }
