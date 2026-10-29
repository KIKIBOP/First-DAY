$ErrorActionPreference = 'Stop'
try {
    $packageRoot = $PSScriptRoot
    $exe = Join-Path $packageRoot 'MediaCollectorHost.exe'
    $runtime = Join-Path $packageRoot 'runtime\python.exe'
    if (-not (Test-Path -LiteralPath $exe) -or -not (Test-Path -LiteralPath $runtime)) {
        throw '包不完整，请完整解压 ZIP 后再运行，不要在压缩软件内直接双击。'
    }
    & $runtime -I (Join-Path $packageRoot 'native-host\portable_check.py')
    if ($LASTEXITCODE -ne 0) { throw '运行环境自检未通过，尚未注册。' }
    $extensionId = (Get-Content -LiteralPath (Join-Path $packageRoot 'extension-id.txt') -Raw).Trim()
    if ($extensionId -cnotmatch '^[a-p]{32}$') { throw '扩展 ID 文件无效' }
    Add-Type -AssemblyName System.Windows.Forms
    $dialog = New-Object System.Windows.Forms.FolderBrowserDialog
    $dialog.Description = '请选择影片保存根目录（不会删除已有文件）'
    $dialog.ShowNewFolderButton = $true
    try {
        if ($dialog.ShowDialog() -ne [System.Windows.Forms.DialogResult]::OK) { throw '已取消，尚未注册。' }
        $saveRoot = $dialog.SelectedPath
    } finally { $dialog.Dispose() }
    & $runtime -I (Join-Path $packageRoot 'native-host\portable_configure.py') $saveRoot
    if ($LASTEXITCODE -ne 0) { throw '保存目录设置失败，尚未注册。' }
    $manifestPath = Join-Path $packageRoot 'com.chrome_media_collector.host.json'
    $manifest = @{
        name='com.chrome_media_collector.host'
        description='Chrome Media Collector Portable'
        path=$exe
        type='stdio'
        allowed_origins=@("chrome-extension://$extensionId/")
    }
    $utf8 = New-Object Text.UTF8Encoding($false)
    [IO.File]::WriteAllText($manifestPath, ($manifest | ConvertTo-Json), $utf8)
    $key='HKCU:\Software\Google\Chrome\NativeMessagingHosts\com.chrome_media_collector.host'
    New-Item -Path $key -Force | Out-Null
    Set-Item -Path $key -Value $manifestPath
    Write-Host ''
    Write-Host '注册完成，无需安装 Python，无需管理员权限。' -ForegroundColor Green
    Write-Host "扩展固定 ID：$extensionId"
    Write-Host "保存根目录：$saveRoot"
    Write-Host '请在 Chrome 的 chrome://extensions 中开启开发者模式，加载本包的 extension 文件夹。'
    Write-Host '然后打开插件设置，确认本地程序已连接，并检测 BitComet。'
    Write-Host '本包移动位置后需重新运行本脚本。真实 Windows 联动仍待真机验证。'
} catch {
    Write-Host $_.Exception.Message -ForegroundColor Red
    exit 1
}
