$ErrorActionPreference = 'Stop'
$key = 'HKCU:\Software\Google\Chrome\NativeMessagingHosts\com.chrome_media_collector.host'
Remove-Item -Path $key -Recurse -Force -ErrorAction SilentlyContinue
$dest = Join-Path $env:LOCALAPPDATA 'ChromeMediaCollector'
foreach ($file in @('MediaCollectorHost.exe','com.chrome_media_collector.host.json')) {
    $p = Join-Path $dest $file
    if (Test-Path -LiteralPath $p) { Remove-Item -LiteralPath $p -Force }
}
Write-Host 'Unregistered host. Settings, logs, task history and all collected media have been preserved.'
Write-Host 'Remove the extension separately in chrome://extensions.'
